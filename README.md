# YouTube Video Extractor

A containerized YouTube downloader using yt-dlp with automated builds and deployment.

## 🚀 Features

- **YouTube video/audio downloads** in native formats and resolutions
- **FFmpeg-enhanced downloads** - combine different video resolutions with best available audio
- **Containerized deployment** with Docker
- **Automatic updates** via Watchtower on Synology NAS
- **CI/CD pipeline** with GitHub Actions
- **Semantic versioning** with automated releases
- **Branch protection** and pull request workflow

## 📋 Prerequisites

- Docker and Docker Compose
- (Optional) Synology NAS with Container Manager for production deployment

## 🛠️ Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/brianfromm/youtube-video-extractor.git
cd youtube-video-extractor

# Build and run locally
docker build -t youtube-extractor-local .
docker run -p 8080:8080 youtube-extractor-local

# Or use Docker Compose
docker-compose up --build
```

### Production Deployment (Synology NAS)

**Container Manager Setup:**

1. **Registry** → Search for `ghcr.io/brianfromm/youtube-video-extractor:latest`
2. **Download** the image
3. **Create container** with port mapping `8080:8080`
4. **Enable auto-restart** and set resource limits
5. **Install Watchtower** for automatic updates

**Watchtower for Auto-Updates:**

```bash
# Create Watchtower container in Container Manager
docker run -d --name watchtower \
  -v /var/run/docker.sock:/var/run/docker.sock \
  containrrr/watchtower --interval 300
```

## 🏗️ Architecture

- **Base**: Python with yt-dlp and FFmpeg
- **Interface**: Simple HTML with Python backend
- **Deployment**: Synology NAS Container Manager
- **Updates**: Watchtower auto-deployment
- **CI/CD**: GitHub Actions with semantic versioning

## 📁 Project Structure

```
youtube-video-extractor/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   └── bug_report.md          # Bug report template
│   └── workflows/
│       ├── docker-build.yml       # Build and push Docker images
│       └── release.yml            # Automated semantic releases
├── docs/
│   └── deployment.md              # Deployment documentation
├── .gitignore                     # Git ignore rules
├── .releaserc.json                # Semantic release configuration
├── docker-compose.yml             # Local development
├── Dockerfile                     # Container definition
├── LICENSE                        # MIT License
├── pull_request_template.md       # PR template
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── server.py                      # Main application server
└── youtube-extractor.html         # Web interface
```

## 🔄 Development Workflow

This project uses a development workflow with branch protection and automated releases.

### Making Changes

1. **Create a feature branch**:

   ```bash
   git checkout main
   git pull origin main
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes and commit using conventional commits**:

   ```bash
   git add .
   git commit -m "feat: add new download format option"
   ```

3. **Push and create a pull request**:

   ```bash
   git push origin feat/your-feature-name
   ```

4. **After PR approval, merge to main** → automatic release and deployment!

### Commit Message Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning:

- `feat:` → Minor version bump (1.0.0 → 1.1.0)
- `fix:` → Patch version bump (1.0.0 → 1.0.1)
- `feat!:` or `BREAKING CHANGE:` → Major version bump (1.0.0 → 2.0.0)
- `docs:`, `style:`, `refactor:`, `test:`, `chore:` → Patch version bump

### Examples:

```bash
feat: add MP3 download support
fix: resolve timeout issue with long videos
docs: update installation instructions
feat!: change API authentication method
```

## 🚀 Deployment

### Automated Deployment

- **Every merge to main** triggers automatic building and deployment
- **Semantic versioning** creates tagged releases automatically
- **Watchtower** pulls and deploys new versions to Synology NAS
- **Zero-downtime updates**

### Manual Deployment

```bash
# Pull latest version manually (if needed)
docker pull ghcr.io/brianfromm/youtube-video-extractor:latest
```

## 🧪 Testing

```bash
# Run tests locally
docker build -t youtube-extractor-test .
docker run --rm youtube-extractor-test pytest

# Test the web interface
curl http://localhost:8080
```

## 📊 Monitoring

- **GitHub Actions** provide build status
- **Synology Container Manager** shows container health and logs
- **Watchtower** handles automatic updates

## 🔧 Configuration

The application runs with sensible defaults. Access the web interface at `http://localhost:8080` after starting the container.

### Docker Compose Override

Create `docker-compose.override.yml` for local customization:

```yaml
version: "3.8"
services:
  youtube-extractor:
    environment:
      - DEBUG=true
    volumes:
      - ./downloads:/downloads
    ports:
      - "3000:8080"
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feat/amazing-feature`)
3. **Commit your changes** using conventional commits
4. **Push to the branch** (`git push origin feat/amazing-feature`)
5. **Open a Pull Request**

### Development Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python server.py

# Test the interface
open http://localhost:8080
```

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes (automatically generated).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [Synology](https://www.synology.com/) - NAS platform
- [GitHub Actions](https://github.com/features/actions) - CI/CD platform

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/brianfromm/youtube-video-extractor/issues)
- **Discussions**: [GitHub Discussions](https://github.com/brianfromm/youtube-video-extractor/discussions)

---

**⭐ Star this repository if you find it useful!**
