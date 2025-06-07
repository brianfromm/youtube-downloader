# YouTube Video Extractor

A web-based tool to extract information and download various formats of YouTube videos, including the ability to manually combine separate high-quality video and audio streams into a single MP4 file. This project was created to practice AI-assisted coding.

## Features

-   **Extract Video Information:** View video title, duration, uploader, view count, and upload date.
-   **List Available Formats:** Displays all available video and audio streams, categorized by type (Video+Audio, Video-Only, Audio-Only).
-   **Direct Downloads:** Download pre-muxed (combined) video/audio, video-only, or audio-only streams directly.
-   **High-Quality Combined Downloads:** Select a high-resolution video-only stream and the best available audio-only stream to combine them into a single, high-quality MP4 file using FFmpeg.
-   **URL Compatibility:** Supports standard `youtube.com/watch?v=` URLs and shortened `youtu.be/` links.
-   **User-Friendly Web Interface:** Simple and intuitive interface to paste a URL and access download options.
-   **Docker Support:** Includes `Dockerfile` and `docker-compose.yml` for easy setup and deployment in a containerized environment.

## Tech Stack

-   **Backend:** Python 3, Flask
-   **Video Processing:** `yt-dlp`, FFmpeg
-   **Frontend:** HTML, CSS (vanilla), JavaScript (vanilla)
-   **Containerization:** Docker, Docker Compose

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

## Setup and Running

### 1. Local Development

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/brianfromm/youtube-video-extractor.git
    cd youtube-video-extractor
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
    git clone https://github.com/brianfromm/youtube-video-extractor.git
    cd youtube-video-extractor
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
3.  Click "Extract Info".
4.  The application will display video details and a list of available download formats.
    -   **High Quality Combined:** Choose a video resolution to combine with the best audio. This process happens on the server and may take some time.
    -   **Video + Audio (Ready to Use):** Direct download for formats that already include audio.
    -   **Video Only / Audio Only:** Direct download for specific video or audio streams.
5.  Click the "Download" or "Combine & Download" buttons for your desired format.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
