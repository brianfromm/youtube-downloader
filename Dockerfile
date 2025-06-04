FROM python:3.12-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY youtube-extractor.html .

# Create temp directory with proper permissions
RUN mkdir -p /tmp/ytextractor && chmod 777 /tmp/ytextractor

# Expose port 8080
EXPOSE 8080

# Use environment variable to determine how to run
CMD if [ "$USE_DEV_SERVER" = "true" ]; then \
        python server.py; \
    else \
        gunicorn --bind 0.0.0.0:8080 --workers 4 --timeout 300 server:app; \
    fi