FROM python:3.12-slim

# Install system dependencies (curl for downloading, ca-certificates for HTTPS, tar and xz-utils for extraction)
# ffmpeg will be installed manually from yt-dlp/FFmpeg-Builds
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    tar \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download and install yt-dlp's FFmpeg build for the designated architecture
# If the build fails at the curl step, manually verify the correct URL from:
# https://github.com/yt-dlp/FFmpeg-Builds/releases/tag/latest
ENV FFMPEG_VERSION_TAG=latest
ARG TARGETARCH # Automatically provided by Docker build for multi-platform builds

RUN \
    echo "Target architecture: ${TARGETARCH}" && \
    if [ "${TARGETARCH}" = "amd64" ]; then \
    FFMPEG_FILENAME="ffmpeg-master-latest-linux64-gpl.tar.xz"; \
    elif [ "${TARGETARCH}" = "arm64" ]; then \
    FFMPEG_FILENAME="ffmpeg-master-latest-linuxarm64-gpl.tar.xz"; \
    else \
    echo "Unsupported architecture: ${TARGETARCH}. FFmpeg will not be installed." >&2; \
    exit 1; \
    fi && \
    FFMPEG_DOWNLOAD_URL="https://github.com/yt-dlp/FFmpeg-Builds/releases/download/${FFMPEG_VERSION_TAG}/${FFMPEG_FILENAME}" && \
    echo "Downloading FFmpeg from ${FFMPEG_DOWNLOAD_URL}" && \
    curl -Lo /tmp/ffmpeg.tar.xz "${FFMPEG_DOWNLOAD_URL}" && \
    mkdir -p /tmp/ffmpeg_extracted && \
    tar -xf /tmp/ffmpeg.tar.xz -C /tmp/ffmpeg_extracted --strip-components=1 && \
    cp /tmp/ffmpeg_extracted/bin/ffmpeg /usr/local/bin/ffmpeg && \
    cp /tmp/ffmpeg_extracted/bin/ffprobe /usr/local/bin/ffprobe && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg.tar.xz /tmp/ffmpeg_extracted && \
    # Verify installation and print version
    echo "FFmpeg version:" && ffmpeg -version && \
    echo "ffprobe version:" && ffprobe -version

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Ensure yt-dlp is the absolute latest version
RUN pip install --no-cache-dir --upgrade yt-dlp[default]

# Copy application files
COPY server.py .
COPY templates/ /app/templates/
COPY static/ /app/static/
COPY favicon.ico .
COPY start.sh .

# Define APP_PORT argument with a default, used if not overridden by docker-compose
ARG APP_PORT=8080

# Make start.sh executable
RUN chmod +x /app/start.sh

# Set the default command to run when the container starts
# This will be overridden by docker-compose if command is specified there
CMD ["/app/start.sh"]

# Expose port (actual port mapping is handled by docker-compose)
EXPOSE ${APP_PORT}