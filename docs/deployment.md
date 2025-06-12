# Deployment Guide: YouTube Video Extractor

This document provides detailed instructions for deploying the YouTube Video Extractor application using Docker and Docker Compose.

## Prerequisites

-   Docker Engine and Docker Compose installed on the deployment server.
-   A pre-built Docker image of the application available (e.g., hosted on GitHub Container Registry, Docker Hub, or built locally on the server).
-   An understanding of environment variables for configuration.

## Standard Deployment (Synology NAS or similar Linux server)

This is the recommended method for deploying on a server like a Synology NAS.

1.  **Prepare the Directory Structure:**
    Create a directory on your server where the application will live, for example:
    ```bash
    mkdir -p /volume1/docker/youtube-extractor
    cd /volume1/docker/youtube-extractor
    ```

2.  **Create `docker-compose.yml`:**
    Place the following `docker-compose.yml` file in this directory:

    ```yaml
    version: '3.8'

    services:
      youtube-extractor:
        image: ${COMPOSE_IMAGE:-ghcr.io/brianfromm/youtube-video-extractor:latest} # Or your specific production image
        container_name: youtube-extractor
        restart: unless-stopped
        ports:
          - "${HOST_PORT:-8080}:${APP_PORT:-8080}"
        volumes:
          - ./processed_files:/app/processed_files # Mount for persistent storage of processed files
        environment:
          - USE_DEV_SERVER=${USE_DEV_SERVER:-false}
          - FLASK_ENV=${FLASK_ENV:-production} # Ensure production mode for Flask
          - GUNICORN_WORKERS=${GUNICORN_WORKERS:-1} # Must be 1
          - GUNICORN_THREADS=${GUNICORN_THREADS:-4}
          - GUNICORN_LOGLEVEL=${GUNICORN_LOGLEVEL:-info}
          - GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-300}
          - APP_PORT=${APP_PORT:-8080}
          # Add any other necessary environment variables
        # healthcheck: # Example if you re-add a healthcheck to docker-compose.yml
        #   test: ["CMD", "curl", "-f", "http://localhost:${APP_PORT:-8080}/health"]
        #   interval: 30s
        #   timeout: 10s
        #   retries: 3
        #   start_period: 30s
    ```

3.  **Create `.env` file:**
    In the same directory (`/volume1/docker/youtube-extractor`), create an `.env` file to specify your production environment variables:

    ```env
    # --- Production .env for YouTube Video Extractor ---

    # Docker Image Configuration
    COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-video-extractor:latest # Replace with your actual production image and tag

    # Docker Build Configuration (primarily for local builds or if building on the server and need to specify target)
    # COMPOSE_PLATFORM=linux/amd64  # Example: For Synology NAS (amd64), often not needed if image is already amd64.
                                   # For ARM-based NAS (like Raspberry Pi or some Synology models), might be linux/arm64/v8.
                                   # Only set if building on this server for a specific arch, or if the pre-built image requires it.
    # COMPOSE_BAKE=true             # Use 'docker buildx bake'. More relevant for the build environment, less so for runtime on server.

    # Application Behavior
    USE_DEV_SERVER=false
    FLASK_ENV=production

    # Gunicorn Configuration (USE_DEV_SERVER=false)
    GUNICORN_WORKERS=1      # IMPORTANT: Must remain 1 due to in-memory task queue
    GUNICORN_THREADS=4      # Adjust based on server CPU cores (e.g., 2-4)
    GUNICORN_LOGLEVEL=info  # Recommended for production (options: debug, info, warning, error)
    GUNICORN_TIMEOUT=300    # Worker timeout in seconds

    # Network Configuration
    APP_PORT=8080           # Internal port the application listens on
    HOST_PORT=8080          # Port on the host machine to access the application
                            # Change if 8080 is already in use on your host
    ```

4.  **Pull the Docker Image (if not building locally on the server):**
    If `COMPOSE_IMAGE` points to a remote registry:
    ```bash
    docker-compose pull
    ```
    Or, more explicitly:
    ```bash
    docker pull ghcr.io/brianfromm/youtube-video-extractor:latest # Or your image
    ```

5.  **Start the Application:**
    ```bash
    docker-compose up -d
    ```
    The `-d` flag runs the container in detached mode (in the background).

6.  **Accessing the Application:**
    Open your web browser and navigate to `http://<your_server_ip>:${HOST_PORT}` (e.g., `http://192.168.1.100:8080`).

7.  **Viewing Logs:**
    ```bash
    docker-compose logs -f youtube-extractor
    ```

8.  **Updating the Application:**
    If you use Watchtower, it can automatically update the image and restart the container when a new version of `COMPOSE_IMAGE` is available.
    Alternatively, to manually update:
    ```bash
    docker-compose pull # Pulls the latest image specified in .env or docker-compose.yml
    docker-compose up -d --remove-orphans # Restarts the service with the new image
    docker image prune -f # Optional: clean up old, unused images
    ```

## Building for a Specific Architecture (Advanced)

If you need to build the Docker image on one machine (e.g., your development Mac) for a different target architecture (e.g., `linux/arm64/v8` for a Raspberry Pi or ARM-based NAS, or `linux/amd64` if your dev machine is ARM):

1.  Ensure Docker Buildx is set up and used on your build machine.
2.  Set `COMPOSE_PLATFORM` in your local build environment's `.env.local` file (or equivalent):
    ```env
    COMPOSE_PLATFORM=linux/arm64/v8 # Or linux/amd64, etc.
    ```
3.  Optionally, enable `docker buildx bake` for potentially faster builds by setting `COMPOSE_BAKE=true` in the same local build environment:
    ```env
    COMPOSE_BAKE=true
    ```
4.  Build the image using `docker-compose build` (if `COMPOSE_BAKE` is set, it might use bake implicitly depending on Compose version) or explicitly with `docker buildx bake ... --push` (if pushing directly to a registry).
5.  Push the multi-arch or specific-arch image to a container registry.
6.  Then, on the target server, ensure `COMPOSE_IMAGE` in its `.env` file points to this correctly tagged, architecture-specific image. The `COMPOSE_PLATFORM` variable on the *target server's* `.env` file is usually not needed if the image is already built for its architecture.

---