#!/usr/bin/env bash
# CanineSense AI — Production Docker Build & Deployment Helper
# Builds production image for linux/amd64 and pushes to Docker Hub for Render deployment.

set -e

echo "=========================================================="
echo " CanineSense AI — Production Docker Container Builder"
echo " Target: linux/amd64 for Render Cloud Deployment"
echo "=========================================================="

if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker is not installed or not in your PATH."
    exit 1
fi

DOCKER_USER="$1"
TAG="${2:-v1.0.0}"

if [ -z "$DOCKER_USER" ]; then
    read -p "Enter your Docker Hub username: " DOCKER_USER
fi

if [ -z "$DOCKER_USER" ]; then
    echo "[ERROR] Docker Hub username is required."
    exit 1
fi

IMAGE_LATEST="${DOCKER_USER}/caninesense-ai:latest"
IMAGE_VERSION="${DOCKER_USER}/caninesense-ai:${TAG}"

echo "1. Building production container image for linux/amd64..."
docker build --platform linux/amd64 -t "$IMAGE_LATEST" -t "$IMAGE_VERSION" -f Dockerfile .

echo "[SUCCESS] Image built successfully: $IMAGE_LATEST and $IMAGE_VERSION"

read -p "Do you want to log in and push this image to Docker Hub now? (y/N): " PUSH
if [[ "$PUSH" =~ ^[Yy]$ ]]; then
    echo "Logging in to Docker Hub..."
    docker login
    echo "Pushing $IMAGE_VERSION..."
    docker push "$IMAGE_VERSION"
    echo "Pushing $IMAGE_LATEST..."
    docker push "$IMAGE_LATEST"
    echo "=========================================================="
    echo " Image successfully published to Docker Hub!"
    echo " Image URL: docker.io/${IMAGE_LATEST}"
    echo "=========================================================="
fi
