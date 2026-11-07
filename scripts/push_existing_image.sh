#!/usr/bin/env bash
# CanineSense AI — Autonomous Tag & Push Helper for Image 1c5007e6ac30
set -e

IMAGE_ID="1c5007e6ac30"
AUTH_FILE="/root/.config/containers/auth.json"

if [ ! -f "$AUTH_FILE" ]; then
    echo "ERROR: Docker Hub authentication not found in $AUTH_FILE."
    echo "Please run: wsl -d Ubuntu -u root -e podman login docker.io"
    exit 1
fi

# Extract username from auth.json if not provided
USER_NAME="$1"
if [ -z "$USER_NAME" ]; then
    AUTH_B64=$(grep -o '"auth": *"[^"]*"' "$AUTH_FILE" | head -n 1 | cut -d'"' -f4)
    if [ -n "$AUTH_B64" ]; then
        USER_NAME=$(echo "$AUTH_B64" | base64 -d | cut -d':' -f1)
    fi
fi

if [ -z "$USER_NAME" ]; then
    echo "ERROR: Could not automatically detect Docker Hub username from credentials."
    exit 1
fi

echo "=========================================================="
echo " Tagging and Pushing Verified Image: $IMAGE_ID"
echo " Target Registry: docker.io/$USER_NAME/caninesense-ai:latest"
echo "=========================================================="

# 1. Tag image
podman tag "$IMAGE_ID" "docker.io/$USER_NAME/caninesense-ai:latest"
podman tag "$IMAGE_ID" "docker.io/$USER_NAME/caninesense-ai:v1.0.0"

# 2. Push image
echo "Pushing image to Docker Hub..."
PUSH_OUTPUT=$(podman push "docker.io/$USER_NAME/caninesense-ai:latest" 2>&1)
echo "$PUSH_OUTPUT"

# 3. Extract digest
DIGEST=$(echo "$PUSH_OUTPUT" | grep -o 'sha256:[a-f0-9]\{64\}' | tail -n 1 || true)
if [ -z "$DIGEST" ]; then
    # Query podman image inspect for repo digest
    DIGEST=$(podman image inspect "docker.io/$USER_NAME/caninesense-ai:latest" --format '{{index .Digest}}' 2>/dev/null || true)
fi

echo "=========================================================="
echo " UPLOAD CONFIRMED BY REGISTRY!"
echo " Image: docker.io/$USER_NAME/caninesense-ai:latest"
echo " Digest: $DIGEST"
echo "=========================================================="
