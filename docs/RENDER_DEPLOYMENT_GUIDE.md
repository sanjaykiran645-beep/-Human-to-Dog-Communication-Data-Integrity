# CanineSense AI — Render Cloud Deployment & Cross-Device Guide

## Overview

CanineSense AI is packaged as a **single, unified, self-contained production service** that serves both the compiled React SPA frontend and the FastAPI/DSP bioacoustic backend on a single HTTPS domain.

This deployment method uses **Render's Native Existing Container Image deployment route**, which **does not require creating or connecting a GitHub repository**.

---

## 1. Architecture & Deployment Flow

```
┌────────────────────────────────────────────────────────┐
│               Local CanineSense Source                 │
│  (React Frontend + FastAPI Backend + Reference Library)│
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            Multi-Stage Dockerfile Build                │
│             Target: linux/amd64                        │
│   Stage 1: Node 20 builds React SPA to /dist           │
│   Stage 2: Python 3.12-slim + FFmpeg + libsndfile      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│      Container Registry (Docker Hub or GHCR)           │
│      docker.io/<username>/caninesense-ai:latest        │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│                 Render Cloud Platform                  │
│       Web Service (Existing Image Deployment)          │
│       Persistent Disk Mount: /app/data (10 GB)         │
│       Public HTTPS URL: https://<app>.onrender.com     │
└────────────────────────────────────────────────────────┘
```

---

## 2. GitHub-Free Deployment Steps

### Step 2.1: Build the Production Container Image

Ensure Docker Desktop is running, then run the build helper script from the `CanineSense_AI` project directory:

**On Windows (PowerShell):**
```powershell
.\scripts\build_docker.ps1 -DockerUser "<your-dockerhub-username>"
```

**On macOS / Linux (Bash):**
```bash
./scripts/build_docker.sh "<your-dockerhub-username>"
```

**Or directly with the Docker CLI:**
```bash
# 1. Build linux/amd64 production image
docker build --platform linux/amd64 -t <your-dockerhub-username>/caninesense-ai:latest -f Dockerfile .

# 2. Log in to Docker Hub
docker login

# 3. Push the image to Docker Hub
docker push <your-dockerhub-username>/caninesense-ai:latest
```

> **Security Note:** The `.dockerignore` file strictly prevents `.env`, `.secret`, `caninesense.sqlite3`, and local user recordings from being baked into the container image.

---

### Step 2.2: Deploy on Render (No GitHub Required)

1. Open your browser and go to the [Render Dashboard](https://dashboard.render.com).
2. Click the **+ New** button in the top right and select **Web Service**.
3. Under the **Source Code** section, select **Existing Image** (do *not* choose Git).
4. In the **Image URL** input, enter:
   ```
   docker.io/<your-dockerhub-username>/caninesense-ai:latest
   ```
   *(If the image is private, click "Add credentials" and provide your Docker Hub username and access token).*
5. Click **Connect**.
6. Set the service settings:
   - **Name:** `caninesense-ai` (or your preferred name)
   - **Region:** Choose the region nearest to you (e.g., `Oregon (US West)` or `Frankfurt (EU)`)
   - **Instance Type:** `Starter` (0.5 CPU, 512 MB or 1 GB RAM recommended for audio DSP workloads)
7. Configure **Environment Variables**:
   | Variable | Value | Description |
   | :--- | :--- | :--- |
   | `CANINESENSE_ENV` | `production` | Enables production security controls |
   | `CANINESENSE_DATA_DIR` | `/app/data` | Path to persistent storage |
   | `CANINESENSE_ACCESS_TOKEN_MINUTES` | `1440` | 24-hour JWT session lifetime |
   | `CANINESENSE_SECRET_KEY` | *(Click "Generate" or enter a 32+ char random string)* | Cryptographic signing key for auth tokens |
8. (Recommended) Configure **Persistent Disk**:
   - Scroll down to the **Disks** section and click **Add Disk**.
   - **Name:** `caninesense-storage`
   - **Mount Path:** `/app/data`
   - **Size:** `10 GB` (provides permanent storage for SQLite user records and user audio recordings across service restarts)
9. Click **Deploy Web Service**.

Render will pull your container, run the health check at `/api/health`, and provide a public HTTPS URL (e.g., `https://caninesense-ai.onrender.com`).

---

## 3. Responsive Desktop & Mobile Experience

The application has been verified across the following viewports:

| Device / Viewport | Width | Layout Behavior |
| :--- | :--- | :--- |
| **Desktop / Laptop** | >1024px | Full 2-column lab layout with permanent sidebar, bento metric tiles, interactive STFT spectrogram viewer, and dual-engine panels. |
| **Tablet / iPad** | 768px – 1024px | Responsive grid wrapping (2 columns), scrollable data tables, touch-friendly audio scrubbing. |
| **iPhone 14/15 Pro Max** | 430px | Single-column stack, collapsible hamburger drawer menu, auto-wrapping audio control buttons. |
| **iPhone 12/13/14/15** | 390px | Compact header title, 16px font inputs to prevent iOS auto-zoom, cross-hair touch STFT display. |
| **Compact Android** | 360px | Full touch-target accessibility (min 42px buttons), horizontal scroll lock (`overflow-x: clip`), responsive WAV download buttons. |

---

## 4. Mobile Installation (PWA / Add to Home Screen)

### On Android (Google Chrome):
1. Navigate to your deployed Render HTTPS URL (e.g. `https://caninesense-ai.onrender.com`).
2. An **"Install app"** banner will appear at the bottom, or tap the three dots **(⋮)** in Chrome and select **"Add to Home screen"** / **"Install app"**.
3. The app will install with its native icon and run in a fullscreen, app-like window.

### On iPhone / iPad (Apple Safari):
1. Open the deployed website in **Safari**.
2. Tap the **Share** button (box with an upward arrow at the bottom of the screen).
3. Scroll down and tap **"Add to Home Screen"**.
4. Confirm the name **CanineSense AI** and tap **Add**.
5. Launch the app from your home screen as a standalone application.

---

## 5. Production Health, Audio & Security Verification

Once deployed to Render, verify the service using these curl checks:

```bash
# 1. Health check
curl -f https://<your-service>.onrender.com/api/health

# 2. Reference library verification
curl -f https://<your-service>.onrender.com/api/communicate/references

# 3. APK package download verification
curl -f -I https://<your-service>.onrender.com/api/download/apk
```

---

## 6. How to Share with Friends & Collaborators

1. Copy your public Render URL: `https://<your-service-name>.onrender.com`.
2. Send the link to your friends or colleagues.
3. Users simply open the link in any browser on their computer, phone, or tablet.
4. They can immediately click **Register**, create their personal account, and start using Engine A (Acoustic Analysis) and Engine B (Vocalization Lab) without installing anything.
