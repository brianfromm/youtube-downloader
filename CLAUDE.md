# YouTube Downloader - Claude Code Reference

## Project Overview
Web-based YouTube video analyzer and downloader built with Flask, yt-dlp, and FFmpeg. Features automated dependency updates and file cleanup for minimal maintenance.

## Key Commands

### Local Development
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run locally
python server.py
# Access: http://localhost:8080
```

### Docker Commands
```bash
# Build and run
docker-compose up --build -d

# Update dependencies manually
docker-compose pull
docker-compose up -d --remove-orphans

# View logs
docker-compose logs -f
```

### GitHub Actions
- **Weekly rebuilds**: Every Sunday 3am MT
- **Manual trigger**: Actions → "Rebuild with Latest Dependencies"
- **Image location**: `ghcr.io/brianfromm/youtube-downloader:latest`

## Important Files
- `server.py` - Main Flask application with task queue
- `.github/workflows/rebuild-dependencies.yml` - Automated dependency updates
- `processed_files/` - Auto-cleaned after 7 days, descriptive filenames
- `PROCESSED_FILES_DIR` - Uses descriptive names like "Title (1080p) [uuid8].mp4"

## Environment Variables
```env
# Production
COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest
USE_DEV_SERVER=false
GUNICORN_WORKERS=1  # MUST be 1 due to in-memory queue
```

## Automation Features
- **File cleanup**: Automatic removal of files older than 7 days
- **Dependency updates**: Weekly yt-dlp and FFmpeg updates via GitHub Actions
- **Descriptive storage**: Files stored with video title + quality info
- **Watchtower ready**: Auto-deployment when new images available

## Architecture Notes
- In-memory task queue (requires single worker)
- Background worker thread for processing
- Dual codec support (direct merge + FFmpeg transcode)
- Mobile-responsive UI (work in progress)