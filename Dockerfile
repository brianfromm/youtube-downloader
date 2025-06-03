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

# Run the application
CMD ["python", "server.py"]