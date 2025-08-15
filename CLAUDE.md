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
python3 server.py
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