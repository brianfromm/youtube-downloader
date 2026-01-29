# YouTube Downloader - Claude Code Reference

## Project Overview

Web-based YouTube video analyzer and downloader built with Flask, yt-dlp, and FFmpeg. Features automated dependency updates and file cleanup for minimal maintenance.

**Requirements:** Python 3.12+, FFmpeg

## Key Commands

### Local Development

```bash
# Setup (one-time)
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Install dev tools (linting, formatting)
pip install -r requirements-dev.txt

# Run locally (always activate venv first)
source venv/bin/activate

# Option 1: Flask dev server (fast restart, may timeout on long downloads)
python server.py

# Option 2: Gunicorn (no timeouts, production-like, recommended for testing)
./start.sh

# Access: http://localhost:8080
```

**Important:** Flask dev server may timeout on long downloads (>3-5 min). For testing large downloads, use Gunicorn via `./start.sh`.

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

- **Weekly rebuilds**: Every Sunday 3am MT (fast 60s builds)
- **Manual trigger**: Actions → "Build and Push Docker Image"
- **Auto-build**: On every push to main
- **Image location**: `ghcr.io/brianfromm/youtube-downloader:latest`

## Important Files

- `server.py` - Main Flask application with task queue
- `.github/workflows/docker-build.yml` - Automated builds and dependency updates
- `processed_files/` - Auto-cleaned after 7 days, descriptive filenames
- `PROCESSED_FILES_DIR` - Uses descriptive names like "Title (1080p) [uuid8].mp4"

## Environment Variables

```env
# Production
COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest
USE_DEV_SERVER=false
GUNICORN_WORKERS=1  # MUST be 1 due to in-memory queue
FORWARDED_ALLOW_IPS=127.0.0.1  # Set to proxy IP/CIDR for proper client IP logging (e.g., 172.19.0.0/16)
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
- Mobile-responsive UI
- Real-time progress tracking with multi-phase UI (Video → Audio → Combining)
- Cancellable downloads with auto-reset after 3 seconds
- Error auto-reset after 5 seconds for failed tasks
- Refactored codebase with helper functions for cleaner maintainability

## PO Token Integration (SABR Workaround)

For videos where YouTube enforces SABR streaming, the application uses:
- **bgutil service**: Generates PO (Proof of Origin) tokens
- **bgutil-ytdlp-pot-provider**: yt-dlp plugin that fetches tokens from bgutil
- **mweb client**: Mobile web client that works with PO tokens
- **Node.js runtime**: Required for JavaScript challenge solving

The bgutil service runs as a separate container and is required for downloading DASH formats (high-quality audio/video) from certain videos.

### Running bgutil Server (for PO Token Support - Local Development)

Some YouTube videos require PO tokens for DASH format downloads. To enable this locally:

```bash
# Clone and build bgutil server (one-time setup)
cd /tmp
git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git bgutil-server
cd bgutil-server/server
npm install && npx tsc

# Start bgutil server (run in separate terminal)
node /tmp/bgutil-server/server/build/main.js
```

The server runs on http://127.0.0.1:4416. The app gracefully degrades if unavailable.

## Commit Patterns (Semantic Release)

Use these commit prefixes for automatic versioning:

### Minor Version Bumps (1.7.x → 1.8.0):

- `feat:` - New features
- `optimize:` - Performance optimizations
- `perf:` - Performance improvements

### Patch Version Bumps (1.7.1 → 1.7.2):

- `fix:` - Bug fixes
- `docs:` - Documentation updates
- `chore:` - Maintenance tasks
- `refactor:` - Code improvements
- `style:` - Code formatting
- `test:` - Test updates
- `security:` - Security patches
- `build:` - Build system changes
- `ci:` - CI/CD changes

### Major Version Bumps (1.x.x → 2.0.0):

- `feat!:` - Breaking changes
- Any type with `BREAKING CHANGE:` in commit body

**Example**: `optimize: streamline Docker build workflow for 13x faster builds`

## Enhanced Release Notes

Release notes now include organized sections with emojis:

- 🚀 Features (feat)
- ⚡ Performance (optimize, perf)
- 🐛 Bug Fixes (fix)
- 🔒 Security (security)
- 📚 Documentation (docs)
- 🔧 Maintenance (chore)
- ♻️ Code Refactoring (refactor)
- 💎 Code Style (style)
- ✅ Tests (test)
- 📦 Build System (build)
- 🔄 CI/CD (ci)
