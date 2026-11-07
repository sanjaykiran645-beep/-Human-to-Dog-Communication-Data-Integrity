# CanineSense AI — Production Docker Build & Deployment Helper
# Builds production image for linux/amd64 and pushes to Docker Hub for Render deployment.

param(
    [Parameter(Mandatory=$false)]
    [string]$DockerUser = "",
    [Parameter(Mandatory=$false)]
    [string]$Tag = "v1.0.0"
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " CanineSense AI — Production Docker Container Builder" -ForegroundColor Cyan
Write-Host " Target: linux/amd64 for Render Cloud Deployment" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Docker CLI is available
$dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerInstalled) {
    Write-Host "[ERROR] Docker is not installed or not in your system PATH." -ForegroundColor Red
    Write-Host "Please install Docker Desktop (from https://www.docker.com/products/docker-desktop/)" -ForegroundColor Yellow
    Write-Host "or install via winget: 'winget install Docker.DockerDesktop'" -ForegroundColor Yellow
    exit 1
}

if ([string]::IsNullOrWhiteSpace($DockerUser)) {
    $DockerUser = Read-Host "Enter your Docker Hub username"
}

if ([string]::IsNullOrWhiteSpace($DockerUser)) {
    Write-Host "[ERROR] Docker Hub username is required to tag the image." -ForegroundColor Red
    exit 1
}

$ImageTagLatest = "$DockerUser/caninesense-ai:latest"
$ImageTagVersion = "$DockerUser/caninesense-ai:$Tag"

Write-Host "`n1. Building production container image for linux/amd64..." -ForegroundColor Green
docker build --platform linux/amd64 -t $ImageTagLatest -t $ImageTagVersion -f Dockerfile .

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Docker build failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`n[SUCCESS] Image built successfully: $ImageTagLatest and $ImageTagVersion" -ForegroundColor Green

$push = Read-Host "`nDo you want to log in and push this image to Docker Hub now? (y/N)"
if ($push -eq 'y' -or $push -eq 'Y') {
    Write-Host "`nLogging in to Docker Hub..." -ForegroundColor Cyan
    docker login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Docker login failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "`nPushing $ImageTagVersion..." -ForegroundColor Cyan
    docker push $ImageTagVersion

    Write-Host "`nPushing $ImageTagLatest..." -ForegroundColor Cyan
    docker push $ImageTagLatest

    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host " Image successfully published to Docker Hub!" -ForegroundColor Green
    Write-Host " Image URL: docker.io/$ImageTagLatest" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "`nNext steps on Render (render.com):" -ForegroundColor Cyan
    Write-Host "1. Log into your Render Dashboard (https://dashboard.render.com)."
    Write-Host "2. Click '+ New' -> 'Web Service'."
    Write-Host "3. Under 'Source Code', select 'Existing Image'."
    Write-Host "4. Enter Image URL: docker.io/$ImageTagLatest"
    Write-Host "5. Set Region: Oregon (or closest to your users)."
    Write-Host "6. Add Environment Variables:"
    Write-Host "   - CANINESENSE_ENV = production"
    Write-Host "   - CANINESENSE_DATA_DIR = /app/data"
    Write-Host "   - CANINESENSE_ACCESS_TOKEN_MINUTES = 1440"
    Write-Host "7. (Recommended) Under 'Disks', add a Persistent Disk with mount path '/app/data'."
    Write-Host "8. Click 'Deploy Web Service'."
} else {
    Write-Host "`nBuild complete. When you are ready to push, run:" -ForegroundColor Yellow
    Write-Host "  docker login"
    Write-Host "  docker push $ImageTagLatest"
}
