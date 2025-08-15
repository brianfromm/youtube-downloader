# YouTube Downloader

A web-based tool to analyze and download various formats of YouTube videos, including the ability to combine separate high-quality video and audio streams into a single MP4 file. This project was created to practice AI-assisted coding.

## Features

-   **Video Analysis:** View video title, duration, uploader, view count, and upload date.
-   **List Available Formats:** Displays all available video and audio streams, categorized by type (Video+Audio, Video-Only, Audio-Only).
-   **Queued Downloads:** Initiate downloads for pre-muxed video/audio, video-only, or audio-only streams. Processing occurs in the background, and the download starts automatically when ready.
-   **High-Quality Combined Downloads:** Select a video-only stream and the best audio to be combined into a high-quality MP4. This task is processed in the background, and the download starts automatically upon completion.
-   **URL Compatibility:** Supports standard `youtube.com/watch?v=` URLs and shortened `youtu.be/` links.
-   **User-Friendly Web Interface:** Simple and intuitive interface to paste a URL and access download options.
-   **Video Thumbnail Preview:** Displays a thumbnail of the YouTube video.
-   **Asynchronous Task Processing:** Downloads and combinations are handled by a background task queue, allowing for a non-blocking user experience.
-   **Automatic File Cleanup:** Automatically removes processed files older than 7 days to manage disk space.
-   **Descriptive File Storage:** Processed files are stored with readable names including video title and quality information.
-   **Automated Dependency Updates:** GitHub Actions workflow automatically rebuilds with latest yt-dlp and FFmpeg weekly.
-   **Docker Support:** Includes `Dockerfile` and `docker-compose.yml` for easy setup and deployment in a containerized environment.

## Tech Stack

-   **Backend:** Python 3, Flask
-   **Video Processing:** `yt-dlp`, FFmpeg
-   **Frontend:** HTML, CSS (vanilla), JavaScript (vanilla)
-   **Containerization:** Docker, Docker Compose

## Project Structure

A brief overview of the key files and directories:

- `server.py`: The main Flask application.
- `templates/`: Contains HTML templates.
  - `youtube-extractor.html`: The main HTML file for the web interface.
- `.github/workflows/`: GitHub Actions automation.
  - `rebuild-dependencies.yml`: Weekly dependency update workflow.
- `static/`: Contains static assets.
  - `css/styles.css`: CSS stylesheets.
  - `js/script.js`: JavaScript code.
- `Dockerfile`: For building the Docker image.
- `docker-compose.yml`: For Docker Compose setup.
- `requirements.txt`: Python dependencies.
- `start.sh`: Script to start the application (dev or prod server) inside Docker.
- `processed_files/`: Directory where processed video/audio files are stored with descriptive names (auto-cleaned after 7 days).

## Prerequisites

### For Local Development:

-   Python 3.8+
-   `pip` (Python package installer)
-   FFmpeg: Must be installed and accessible in your system's PATH. This is crucial for the video/audio combination feature.
    -   **macOS:** `brew install ffmpeg`
    -   **Linux (Debian/Ubuntu):** `sudo apt update && sudo apt install ffmpeg`
    -   **Windows:** Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH.
-   Git (for cloning the repository)

### For Docker Deployment:

-   Docker Desktop or Docker Engine/CLI.

## Configuration (.env files)

This project uses environment variables to manage Docker configurations for different environments (like local development vs. production). These variables can be set in `.env` files.

- **`.env.local` (for Local Development):** Create this file in the project root for your local setup. It is ignored by Git. This is where you'd specify settings for local builds.
- **`.env` (for Production/Server):** On your production server (e.g., Synology NAS), you can place a `.env` file in the directory where Docker Compose is run. Docker Compose automatically loads variables from a file named `.env`.

Available environment variables:

- **`COMPOSE_IMAGE`**:
  - **Purpose:** Specifies the Docker image name and tag to use.
  - **Local Development (in `.env.local`):** Set to a local-specific tag, e.g., `COMPOSE_IMAGE=youtube-extractor-local:latest`. When you run `docker-compose build`, the locally built image will be tagged with this name.
  - **Production (in `.env` on server):** Set to your pre-built production image URL, e.g., `COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest`. This allows Watchtower (or manual pulls) to use the correct production image.
  - **Default (if not set):** Defaults to `youtube-extractor-default:latest` in `docker-compose.yml`, intended for local builds if no specific `COMPOSE_IMAGE` is provided.

- **`COMPOSE_PLATFORM`**:
  - **Purpose:** Specifies the target platform for Docker image builds (e.g., `linux/amd64`, `linux/arm64/v8`).
  - **Usage (typically in `.env.local` for cross-compilation or specific architecture builds):** For Apple Silicon Macs building for a Linux ARM target, you might set `COMPOSE_PLATFORM=linux/arm64/v8`. For building for a standard AMD64/x86-64 Linux target, set `COMPOSE_PLATFORM=linux/amd64`.
  - **Default (if not set):** Defaults to `linux/amd64` in `docker-compose.yml`.

- **`COMPOSE_BAKE`**:
  - **Purpose:** Tells Docker Compose to use `docker buildx bake` for building images, which can offer performance improvements and access to advanced BuildKit features.
  - **Usage:** Set to `true` (e.g., `COMPOSE_BAKE=true` in `.env.local` or `.env`) to enable.
  - **Default (if not set):** Docker Compose uses its standard build process. Enabling is generally recommended for potentially faster and more efficient builds.

- **`USE_DEV_SERVER`**:
  - **Purpose:** Controls whether the Flask development server or a production server (Gunicorn) is used inside the container. When `true`, `FLASK_ENV` is also set to `development` within `start.sh`.
  - **Usage:** Set to `true` (e.g., `USE_DEV_SERVER=true` in `.env.local`) to use the Flask development server (useful for debugging). Set to `false` (e.g., `USE_DEV_SERVER=false` in `.env` on server) to use Gunicorn for production.
  - **Default (if not set):** Defaults to `false` in `docker-compose.yml`, meaning Gunicorn will be used.

- **`GUNICORN_WORKERS`**:
  - **Purpose:** Sets the number of Gunicorn worker processes when `USE_DEV_SERVER` is `false`.
  - **Usage:** E.g., `GUNICORN_WORKERS=1`.
  - **IMPORTANT NOTE:** Due to the current in-memory task queue implementation, **this value MUST be set to `1` (or left unset to use the default of `1`)**. Using more than one worker will lead to inconsistent behavior as each worker would have its own separate task queue and status.
  - **Default (if not set):** Defaults to `1` in `start.sh`.

- **`GUNICORN_THREADS`**:
  - **Purpose:** Sets the number of threads per Gunicorn worker process when `USE_DEV_SERVER` is `false`. This allows a single worker to handle multiple requests concurrently, especially useful for I/O-bound operations.
  - **Usage:** E.g., `GUNICORN_THREADS=4`.
  - **Default (if not set):** Defaults to `4` in `start.sh`.

- **`GUNICORN_TIMEOUT`**:
  - **Purpose:** Sets the timeout in seconds for Gunicorn workers when `USE_DEV_SERVER` is `false`.
  - **Usage:** E.g., `GUNICORN_TIMEOUT=300` (for 5 minutes).
  - **Default (if not set):** Defaults to `300` in `start.sh`.

- **`GUNICORN_LOGLEVEL`**:
  - **Purpose:** Sets the log level for Gunicorn when `USE_DEV_SERVER` is `false`.
  - **Usage:** E.g., `GUNICORN_LOGLEVEL=info`. Common values: `debug`, `info`, `warning`, `error`.
  - **Default (if not set):** Defaults to `info` in `start.sh`.

- **`APP_PORT`**:
  - **Purpose:** Defines the port number that the application (Flask/Gunicorn) listens on *inside* the Docker container.
  - **Usage:** E.g., `APP_PORT=8080`.
  - **Default (if not set):** Defaults to `8080` (used in `start.sh` and as a `Dockerfile` ARG).

- **`HOST_PORT`**:
  - **Purpose:** Defines the port number on the *host machine* that maps to the `APP_PORT` inside the container (defined in `docker-compose.yml`).
  - **Usage:** E.g., `HOST_PORT=8000` (would map port 8000 on host to `APP_PORT` in container).
  - **Default (if not set):** Defaults to the value of `APP_PORT` in `docker-compose.yml` (so if `APP_PORT` is 8080 and `HOST_PORT` is not set, the mapping will be `8080:8080`).

**Example `.env.local` for an Apple Silicon Mac developer:**
```
COMPOSE_IMAGE=youtube-extractor-local:latest
COMPOSE_PLATFORM=linux/arm64/v8 # Or linux/amd64 if building for that target
COMPOSE_BAKE=true # Enable Docker Buildx Bake for building
USE_DEV_SERVER=true
# GUNICORN_WORKERS=1 # Must be 1 if testing Gunicorn locally due to in-memory queue
# GUNICORN_THREADS=4 # Optional: override default for local Gunicorn testing
# GUNICORN_LOGLEVEL=debug # Optional: override default for verbose local Gunicorn testing
# GUNICORN_TIMEOUT=120 # Optional: override default for local Gunicorn testing
# APP_PORT=8080 # Optional: override default internal port
# HOST_PORT=8080 # Optional: override default host port mapping
```

**Example `.env` for a production Synology NAS (amd64):**
```
COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest
USE_DEV_SERVER=false
GUNICORN_WORKERS=1 # IMPORTANT: Must be 1 due to in-memory task queue
GUNICORN_THREADS=4 # Default, can be adjusted based on NAS performance
GUNICORN_LOGLEVEL=info # Default, can be changed to 'warning' for quieter logs
GUNICORN_TIMEOUT=300 # Default
APP_PORT=8080 # Standard internal port
HOST_PORT=8080 # Standard host mapping for this service
# COMPOSE_PLATFORM=linux/amd64 # Usually not needed if building on/for amd64, or if image is pre-built for amd64
```

## Setup and Running

### 1. Local Development

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/brianfromm/youtube-downloader.git
    cd youtube-downloader
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ensure FFmpeg is installed and in your PATH.**
    Verify by typing `ffmpeg -version` in your terminal.

5.  **Run the Flask server:**
    ```bash
    python server.py
    ```

6.  Open your web browser and navigate to `http://localhost:8080` or `http://0.0.0.0:8080`.

### 2. Using Docker

1.  **Clone the repository (if not already done):**
    ```bash
    git clone https://github.com/brianfromm/youtube-downloader.git
    cd youtube-downloader
    ```

2.  **Using `docker-compose` (recommended for Docker):**
    This will build the image and run the container.
    ```bash
    docker-compose up --build
    ```

    To run in detached mode:
    ```bash
    docker-compose up --build -d
    ```

3.  **Alternatively, build and run manually:**
    *   **Build the Docker image:**
        ```bash
        docker build -t youtube-extractor .
        ```
    *   **Run the Docker container:**
        ```bash
        docker run -p 8080:8080 youtube-extractor
        ```

4.  Open your web browser and navigate to `http://localhost:8080`.

## How to Use

1.  Open the web application in your browser.
2.  Paste a YouTube video URL (e.g., `https://www.youtube.com/watch?v=dQw4w9WgXcQ` or `https://youtu.be/dQw4w9WgXcQ`) into the input field.
3.  Click "Analyze Video".
4.  The application will display video details and a list of available download formats.
    -   **High Quality Combined:** Choose a video resolution to combine with the best audio. The button will show processing status, and the download will start automatically once the file is ready.
    -   **Video + Audio (Ready to Use):** Direct download for formats that already include audio.
    -   **Video Only / Audio Only:** Direct download for specific video or audio streams.
5.  Click the "Download" or "Combine & Download" button for your desired format. The button will update to show the task status (e.g., "Queued...", "Processing..."). Once server-side processing is complete, the file download will begin automatically in your browser.

## Automated Maintenance

The application includes several automated features for minimal-maintenance operation:

### **Dependency Updates**
- **Weekly rebuilds**: GitHub Actions automatically rebuilds the Docker image every Sunday at 3am Mountain Time with the latest yt-dlp and FFmpeg versions
- **Manual triggers**: Updates can be triggered manually via GitHub Actions when YouTube makes breaking changes
- **Watchtower integration**: If using Watchtower, your containers will automatically update when new images are available

### **File Management**
- **Automatic cleanup**: Processed files are automatically removed after 7 days to prevent disk space issues
- **Descriptive naming**: Files are stored with readable names like `"Video Title (1080p) [uuid8].mp4"` for easy identification
- **Background processing**: All cleanup happens automatically without interrupting downloads

## Disclaimer

This YouTube Downloader is provided for educational, personal, and demonstration purposes only. By using this tool, you agree that you are solely responsible for:

-   Ensuring your use of this tool and any content downloaded complies with all applicable local, state, national, and international laws, including but not limited to copyright laws.
-   Adhering to the terms of service of YouTube (or any other content provider).
-   Respecting the intellectual property rights of content creators.

The developers of this tool assume no responsibility for how this tool is used or for any copyright infringement. Misuse of this tool to download or distribute copyrighted material without permission is strictly prohibited.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
