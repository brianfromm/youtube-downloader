# YouTube Downloader - Claude Code Reference

## Project Overview

Web-based YouTube video analyzer and downloader built with Flask, yt-dlp, and FFmpeg. Features automated dependency updates and file cleanup for minimal maintenance.

**Requirements:** Python 3.14+, FFmpeg

## Key Commands

### Local Development

```bash
# Setup (one-time)
python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Install dev tools (ruff, pylint, mypy)
pip install -r requirements-dev.txt

# Run locally (always activate venv first)
source venv/bin/activate

# Terminal 1: Start bgutil PO token server (required for all DASH formats)
node ~/.local/share/bgutil-server/server/build/main.js

# Terminal 2: Start the app
./start.sh          # Gunicorn (recommended, no timeouts)
# or: python server.py  # Flask dev server (fast restart, may timeout on long downloads)

# Access: http://localhost:8080
```

**Important:** Without the bgutil token server, most videos will only show a single format. With it running, all DASH formats (video resolutions, audio qualities, MP3) become available. See [PO Token Integration](#po-token-integration-sabr-workaround) for one-time setup.

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

### Linting and Formatting

Ruff handles both linting and formatting.

```bash
source venv/bin/activate

ruff check .            # Lint
ruff check . --fix      # Lint and autofix
ruff format .           # Format
ruff format --check .   # Verify formatting (what CI runs)
```

**Note:** Ruff formats Python code blocks inside Markdown files as well as `.py`
files, so `docs/*.md`, `README.md`, and `CLAUDE.md` are all covered. Config lives
in `pyproject.toml` under `[tool.ruff]`; `venv/` is excluded by default.

### GitHub Actions

- **Lint and format**: Runs `ruff check` and `ruff format --check` on every push and PR to main
- **Weekly rebuilds**: Every Sunday 3am MT (fast 60s builds)
- **Manual trigger**: Actions → "Build and Push Docker Image"
- **Auto-build**: On every push to main
- **Image location**: `ghcr.io/brianfromm/youtube-downloader:latest`

## Important Files

- `server.py` - Main Flask application with task queue
- `.github/workflows/docker-build.yml` - Automated builds and dependency updates
- `.github/workflows/lint.yml` - Ruff lint and format checks on push/PR
- `processed_files/` - Auto-cleaned after 7 days, descriptive names like "Title (1080p) [uuid8].mp4"

## Environment Variables

```env
# Production
COMPOSE_IMAGE=ghcr.io/brianfromm/youtube-downloader:latest
USE_DEV_SERVER=false
GUNICORN_WORKERS=1  # MUST be 1 due to in-memory queue
FORWARDED_ALLOW_IPS=127.0.0.1  # Set to proxy IP/CIDR for proper client IP logging (e.g., 172.19.0.0/16)
```

## Architecture Notes

- In-memory task queue (requires single worker)
- Background worker thread for processing
- Dual codec support (direct merge + FFmpeg transcode)
- Mobile-responsive UI with real-time progress tracking (Video → Audio → Combining)

## PO Token Integration (SABR Workaround)

For videos where YouTube enforces SABR streaming, the application uses:

- **bgutil service**: Generates PO (Proof of Origin) tokens
- **bgutil-ytdlp-pot-provider**: yt-dlp plugin that fetches tokens from bgutil
- **mweb client**: Mobile web client that works with PO tokens
- **Node.js runtime**: Required for JavaScript challenge solving

The bgutil service runs as a separate container and is required for downloading DASH formats (high-quality audio/video) from certain videos.

### bgutil Server Setup (One-Time)

```bash
mkdir -p ~/.local/share
cd ~/.local/share
git clone https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git bgutil-server
cd bgutil-server/server
npm install && npx tsc
```

The server runs on <http://127.0.0.1:4416>. The app gracefully degrades if unavailable —
but degraded means most videos expose only a single low-res format, so start it first.

**Do not install this under `/tmp`.** macOS purges `/tmp`, so the build silently disappears
and DASH formats stop appearing with no obvious cause. `~/.local/share` persists.

Verify it is up: `curl -s http://127.0.0.1:4416/ping`

## Commit Patterns (Semantic Release)

Use these commit prefixes for automatic versioning:

### Minor Version Bumps (1.7.x → 1.8.0)

- `feat:` - New features
- `optimize:` - Performance optimizations
- `perf:` - Performance improvements

### Patch Version Bumps (1.7.1 → 1.7.2)

- `fix:` - Bug fixes
- `docs:` - Documentation updates
- `chore:` - Maintenance tasks
- `refactor:` - Code improvements
- `style:` - Code formatting
- `test:` - Test updates
- `security:` - Security patches
- `build:` - Build system changes
- `ci:` - CI/CD changes

### Major Version Bumps (1.x.x → 2.0.0)

- `feat!:` - Breaking changes
- Any type with `BREAKING CHANGE:` in commit body

**Example**: `optimize: streamline Docker build workflow for 13x faster builds`
