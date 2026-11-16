# Deployment Guide: YouTube Video Downloader

This guide covers deploying the published Docker image with Docker Compose on a Linux server.

## Prerequisites

- Docker Engine with the Compose plugin (`docker compose`) on the server
- Network access to `ghcr.io` to pull the published image

## How the configuration works

The repository's [`docker-compose.yml`](../docker-compose.yml) is deployed **as-is**. Every
environment-specific value is a `${VAR}` with a default, so you never edit the compose file on
the server. Anything specific to your host goes in a `.env` file next to it.

The compose file runs two services:

- **`bgutil`**: generates PO (Proof of Origin) tokens. Without it, most videos expose only a
  single low-resolution format instead of the full set of DASH video and audio formats. The app
  waits for this service to report healthy before it starts.
- **`youtube-downloader`**: the app itself, served by Gunicorn.

`docker-compose.dev.yml` adds a `build:` section for building from source and is for local
development only. Don't copy it to a server.

## Standard deployment

1. **Create a directory** for the app on your server and change into it:

   ```bash
   mkdir -p <app-dir>
   cd <app-dir>
   ```

2. **Copy `docker-compose.yml`** from this repository into that directory, unchanged.

3. **Create a `.env` file** in the same directory with only the values your host needs to
   override. Everything is optional; the defaults are shown:

   ```env
   # Image to run
   COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest

   # Network
   BIND_ADDRESS=0.0.0.0   # Set to one host interface's IP to restrict the listener
   HOST_PORT=8080         # Port on the host
   APP_PORT=8080          # Port inside the container

   # Where processed files appear on the host
   PROCESSED_DIR=./processed_videos_host

   # Gunicorn
   GUNICORN_WORKERS=1     # Must stay 1: the task queue is in-memory
   GUNICORN_THREADS=4
   GUNICORN_TIMEOUT=0     # 0 = no timeout, so long downloads are never killed
   GUNICORN_LOGLEVEL=info

   # Behind a reverse proxy, set this to the proxy's IP or network CIDR so logs show
   # the real client address instead of the proxy's. Find a Docker network's CIDR with:
   #   docker network inspect <network> -f '{{range .IPAM.Config}}{{.Subnet}}{{end}}'
   FORWARDED_ALLOW_IPS=127.0.0.1
   ```

   `.env` is gitignored. Never commit a host's real values to the repository.

4. **Start the stack:**

   ```bash
   docker compose pull
   docker compose up -d
   ```

5. **Open the app** at `http://<server-address>:<HOST_PORT>`.

6. **View logs:**

   ```bash
   docker compose logs -f
   ```

## Updating

### Image updates

Every push to `main` and a weekly scheduled rebuild publish a new image. The app service carries
a Watchtower label (`com.centurylinklabs.watchtower.enable=true`), so if you run
[Watchtower](https://containrrr.dev/watchtower/) it pulls and restarts automatically. To update
manually:

```bash
docker compose pull
docker compose up -d --remove-orphans
docker image prune -f   # Optional: remove old images
```

### Compose file updates

Nothing syncs `docker-compose.yml` itself. Image updates arrive automatically, but a change to the
compose file only reaches the server if you copy the new file over and re-run:

```bash
docker compose up -d
```

Update the compose file this way rather than hand-editing the server's copy. A hand-edited copy
silently drifts from the repository, and later changes to the repository version won't reach it.

## Building for a specific architecture (advanced)

The published image is built for `linux/amd64` only. To run on an ARM server, build your own
image for that architecture:

1. Make sure Docker Buildx is set up on the build machine.
2. Build and push for the target platform:

   ```bash
   docker buildx build --platform linux/arm64 -t <registry>/<image>:<tag> --push .
   ```

3. On the server, set `COMPOSE_IMAGE=<registry>/<image>:<tag>` in `.env`.
