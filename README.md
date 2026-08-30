# YouTube Downloader

A web-based tool to analyze and download various formats of YouTube videos, including the ability to combine separate high-quality video and audio streams into a single MP4 file.

This project started from a need to occasionally download videos without relying on sketchy online sites filled with malware and ads. What began as a simple AI-assisted coding practice project evolved alongside building a home lab—starting with a Synology NAS and expanding into a full server setup hosting multiple projects. The weekly automated rebuilds ensure the latest yt-dlp and FFmpeg versions are always available, keeping the tool working as YouTube evolves.

## Features

- **Video Analysis:** View title, duration, uploader, view count, and upload date with thumbnail preview.
- **Format Selection:** Browse all available streams categorized by type (Video+Audio, Video-Only, Audio-Only).
- **High-Quality Combined Downloads:** Select a video-only stream and the best audio to be combined into a single MP4.
- **Real-Time Progress:** Visual progress bars with phase indicators (Video → Audio → Combining) and cancellable at any time.
- **URL Compatibility:** Supports `youtube.com/watch?v=`, `youtu.be/`, `/live/`, `/shorts/`, `/embed/`, `/v/`, and `m.youtube.com` URLs.
- **Mobile-Responsive UI:** Fully optimized for mobile devices with touch-friendly controls.
- **Background Processing:** Async task queue with automatic file cleanup (7 days) and descriptive filenames.
- **Automated Updates:** Weekly GitHub Actions rebuilds with latest yt-dlp and FFmpeg.
- **SABR Streaming Support:** Handles YouTube's SABR restrictions via PO token generation.
- **Docker Support:** Includes `Dockerfile` and `docker-compose.yml` for containerized deployment.

## Tech Stack

- **Backend:** Python 3.14+, Flask
- **Video Processing:** `yt-dlp`, FFmpeg
- **PO Token Support:** `bgutil-ytdlp-pot-provider` (for SABR streaming workaround)
- **Frontend:** HTML, CSS (vanilla), JavaScript (vanilla)
- **Containerization:** Docker, Docker Compose

## Project Structure

A brief overview of the key files and directories:

- `server.py`: The main Flask application.
- `templates/`: Contains HTML templates.
  - `youtube-downloader.html`: The main HTML file for the web interface.
- `.github/workflows/`: GitHub Actions automation.
  - `docker-build.yml`: Automated builds and weekly dependency updates.
- `static/`: Contains static assets.
  - `css/styles.css`: CSS stylesheets.
  - `js/script.js`: JavaScript code.
- `Dockerfile`: For building the Docker image.
- `docker-compose.yml`: Base Compose file, deployed to servers as-is.
- `docker-compose.dev.yml`: Local overlay that builds from source.
- `requirements.txt`: Python dependencies.
- `start.sh`: Script to start the application (dev or prod server) inside Docker.
- `processed_files/`: Directory where processed video/audio files are stored with descriptive names (auto-cleaned after 7 days).

## Prerequisites

### For Local Development

- Python 3.14+
- `pip` (Python package installer)
- FFmpeg: Must be installed and accessible in your system's PATH. This is crucial for the video/audio combination feature.
  - **macOS:** `brew install ffmpeg`
  - **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ffmpeg`
  - **Windows:** Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH.
- Git (for cloning the repository)

### For Docker Deployment

- Docker Desktop or Docker Engine/CLI.

## Configuration (.env files)

This project uses environment variables to manage Docker configurations for different environments (like local development vs. production). These variables can be set in `.env` files.

- **`.env.local` (for Local Development):** Create this file in the project root for your local setup. It is ignored by Git. This is where you'd specify settings for local builds.
- **`.env` (for Production/Server):** On your production server (e.g., Synology NAS), you can place a `.env` file in the directory where Docker Compose is run. Docker Compose automatically loads variables from a file named `.env`.

Available environment variables:

| Variable              | Default                             | Description                                                                                  |
| --------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------- |
| `COMPOSE_IMAGE`       | `youtube-downloader-default:latest` | Docker image name/tag. Set to `ghcr.io/brianfromm/youtube-downloader:latest` for production. |
| `COMPOSE_PLATFORM`    | `linux/amd64`                       | Target platform for builds (e.g., `linux/arm64/v8` for Apple Silicon).                       |
| `COMPOSE_BAKE`        | _(disabled)_                        | Set `true` to use `docker buildx bake` for faster builds.                                    |
| `USE_DEV_SERVER`      | `false`                             | Set `true` for Flask dev server; `false` for Gunicorn.                                       |
| `GUNICORN_WORKERS`    | `1`                                 | Worker processes. **Must be 1** due to in-memory task queue.                                 |
| `GUNICORN_THREADS`    | `4`                                 | Threads per worker for concurrent request handling.                                          |
| `GUNICORN_TIMEOUT`    | `0` (unlimited)                     | Worker timeout in seconds. `0` recommended for video downloads.                              |
| `GUNICORN_LOGLEVEL`   | `info`                              | Log level: `debug`, `info`, `warning`, `error`.                                              |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1`                         | Trusted proxy IPs/CIDRs for `X-Forwarded-*` headers. Set to your proxy's network CIDR.       |
| `APP_PORT`            | `8080`                              | Port the app listens on inside the container.                                                |
| `HOST_PORT`           | _(same as APP_PORT)_                | Port on the host machine mapped to `APP_PORT`.                                               |

**Example `.env.local` for an Apple Silicon Mac developer:**

```bash
COMPOSE_IMAGE=youtube-downloader-local:latest
COMPOSE_PLATFORM=linux/arm64/v8 # Or linux/amd64 if building for that target
COMPOSE_BAKE=true # Enable Docker Buildx Bake for building
USE_DEV_SERVER=true
# GUNICORN_WORKERS=1 # Must be 1 if testing Gunicorn locally due to in-memory queue
# GUNICORN_THREADS=4 # Optional: override default for local Gunicorn testing
# GUNICORN_LOGLEVEL=debug # Optional: override default for verbose local Gunicorn testing
# GUNICORN_TIMEOUT=0 # Optional: 0 = unlimited (recommended for large files), or set specific seconds
# FORWARDED_ALLOW_IPS=127.0.0.1 # Optional: set proxy IP/CIDR if behind reverse proxy
# APP_PORT=8080 # Optional: override default internal port
# HOST_PORT=8080 # Optional: override default host port mapping
```

**Example `.env` for a production Synology NAS (amd64):**

```bash
COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest
USE_DEV_SERVER=false
GUNICORN_WORKERS=1 # IMPORTANT: Must be 1 due to in-memory task queue
GUNICORN_THREADS=4 # Default, can be adjusted based on NAS performance
GUNICORN_LOGLEVEL=info # Default, can be changed to 'warning' for quieter logs
GUNICORN_TIMEOUT=0 # Default: 0 = unlimited timeout (recommended for large video files)
# FORWARDED_ALLOW_IPS= # Optional: your reverse proxy's Docker network CIDR (docker network inspect <network>)
APP_PORT=8080 # Standard internal port
HOST_PORT=8080 # Standard host mapping for this service
# COMPOSE_PLATFORM=linux/amd64 # Usually not needed if building on/for amd64, or if image is pre-built for amd64
```

## Setup and Running

### 1. Local Development

1. **Clone the repository:**

   ```bash
   git clone https://github.com/brianfromm/youtube-downloader.git
   cd youtube-downloader
   ```

2. **Create and activate a virtual environment (recommended):**

   ```bash
   python3.14 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt

   # Optional: Install development tools (linting, formatting)
   pip install -r requirements-dev.txt
   ```

4. **Ensure FFmpeg is installed and in your PATH.**
   Verify by typing `ffmpeg -version` in your terminal.

5. **Start the bgutil PO token server (recommended):**

   Without this server, most videos will only show a single download format. With it running, all DASH formats (multiple resolutions, audio qualities, MP3) become available.

   ```bash
   # One-time setup
   cd /tmp
   git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git bgutil-server
   cd bgutil-server/server
   npm install && npx tsc

   # Start the server (run in a separate terminal)
   node /tmp/bgutil-server/server/build/main.js
   ```

   The server runs on `http://127.0.0.1:4416`. The app gracefully degrades if it's not available.

6. **Run the app (in another terminal):**

   ```bash
   cd youtube-downloader
   source venv/bin/activate
   ./start.sh          # Gunicorn (recommended, no timeouts)
   # or: python server.py  # Flask dev server (fast restart, may timeout on long downloads)
   ```

7. Open your web browser and navigate to `http://localhost:8080`.

### 2. Using Docker

1. **Clone the repository (if not already done):**

   ```bash
   git clone https://github.com/brianfromm/youtube-downloader.git
   cd youtube-downloader
   ```

2. **Using Docker Compose (recommended for Docker):**
   This builds the image and runs the container, including the bgutil service for PO token support.

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
   ```

   To run in detached mode, add `-d`.

   `docker-compose.yml` on its own runs the published image and is what gets
   deployed to a server unchanged; `docker-compose.dev.yml` is the local overlay
   that builds from source.

   **Note:** The bgutil service starts automatically and enables downloads from videos with SABR streaming restrictions.

3. **Alternatively, build and run manually:**
   - **Build the Docker image:**

     ```bash
     docker build -t youtube-downloader .
     ```

   - **Run the Docker container:**

     ```bash
     docker run -p 8080:8080 youtube-downloader
     ```

4. Open your web browser and navigate to `http://localhost:8080`.

## How to Use

1. Open the web application in your browser.
2. Paste a YouTube video URL (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ`, `https://youtu.be/dQw4w9WgXcQ`, or `https://www.youtube.com/live/dQw4w9WgXcQ`) into the input field.
3. Click "Analyze Video".
4. The application will display video details and a list of available download formats.
   - **High Quality Combined:** Choose a video resolution to combine with the best audio. The button will show processing status with a multi-phase progress bar (Video → Audio → Combining), and the download will start automatically once the file is ready.
   - **Video + Audio (Direct Download):** Direct download for formats that already include audio, with a streamlined single progress bar.
   - **Video Only / Audio Only:** Direct download for specific video or audio streams with single progress bar.
5. Click the "Download" or "Combine & Download" button for your desired format. The button will immediately change to "Cancel" and show a progress section indicating the current status (Queued, Downloading, Processing, etc.) with real-time progress tracking.
6. **Cancel anytime:** Click the "Cancel" button to stop a queued or in-progress download. A confirmation dialog will appear to confirm your choice. Cancelled tasks automatically reset after 3 seconds, allowing you to try again.
7. **Automatic retry:** If a download fails, the error message will display for 5 seconds before automatically resetting the button for easy retry.
8. Once server-side processing is complete, the file download will begin automatically in your browser.

## Disclaimer

This YouTube Downloader is provided for educational, personal, and demonstration purposes only. By using this tool, you agree that you are solely responsible for:

- Ensuring your use of this tool and any content downloaded complies with all applicable local, state, national, and international laws, including but not limited to copyright laws.
- Adhering to the terms of service of YouTube (or any other content provider).
- Respecting the intellectual property rights of content creators.

The developers of this tool assume no responsibility for how this tool is used or for any copyright infringement. Misuse of this tool to download or distribute copyrighted material without permission is strictly prohibited.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
