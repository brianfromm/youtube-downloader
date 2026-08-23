FROM python:3.14-slim

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
    CHECKSUMS_URL="https://github.com/yt-dlp/FFmpeg-Builds/releases/download/${FFMPEG_VERSION_TAG}/checksums.sha256" && \
    echo "Downloading FFmpeg from ${FFMPEG_DOWNLOAD_URL}" && \
    curl -Lo "/tmp/${FFMPEG_FILENAME}" "${FFMPEG_DOWNLOAD_URL}" && \
    # Verify against the checksums published alongside the same release. The tag is
    # rolling, so this catches a corrupted or truncated transfer, not a bad upstream.
    curl -Lo /tmp/checksums.sha256 "${CHECKSUMS_URL}" && \
    awk -v f="${FFMPEG_FILENAME}" '$2 == f' /tmp/checksums.sha256 > /tmp/ffmpeg.expected.sha256 && \
    test -s /tmp/ffmpeg.expected.sha256 && \
    (cd /tmp && sha256sum -c ffmpeg.expected.sha256) && \
    mkdir -p /tmp/ffmpeg_extracted && \
    tar -xf "/tmp/${FFMPEG_FILENAME}" -C /tmp/ffmpeg_extracted --strip-components=1 && \
    cp /tmp/ffmpeg_extracted/bin/ffmpeg /usr/local/bin/ffmpeg && \
    cp /tmp/ffmpeg_extracted/bin/ffprobe /usr/local/bin/ffprobe && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf "/tmp/${FFMPEG_FILENAME}" /tmp/ffmpeg_extracted /tmp/checksums.sha256 /tmp/ffmpeg.expected.sha256 && \
    # Verify installation and print version
    echo "FFmpeg version:" && ffmpeg -version && \
    echo "ffprobe version:" && ffprobe -version

# Install Node.js for yt-dlp JavaScript challenge solving (required for PO token support)
# Use NodeSource to get a proper Node.js installation without permission restrictions
RUN apt-get update && apt-get install -y \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip to latest version first
RUN pip install --no-cache-dir --upgrade --root-user-action=ignore pip

# Install Python dependencies
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
# Ensure yt-dlp is the absolute latest version
RUN pip install --no-cache-dir --upgrade --root-user-action=ignore yt-dlp[default]

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