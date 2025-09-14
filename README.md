# Instagram Content Generator

An automated Instagram content generator that uses AI to analyze images and videos, generate engaging captions, and automatically post content to Instagram. Designed for easy deployment on Raspberry Pi with Docker.

## 🌟 Features

- **AI-Powered Content Analysis**: Uses computer vision models (CLIP, BLIP) to understand image/video content
- **Dynamic Caption Generation**: Creates engaging captions using OpenAI GPT models with hashtags and emojis
- **Automated File Monitoring**: Watches shared folders for new content and processes automatically
- **Multi-User Support**: Manages content for multiple Instagram accounts
- **Raspberry Pi Optimized**: Lightweight Docker containers with ARM64 support
- **Health Monitoring**: Built-in health checks and system monitoring
- **Rate Limiting**: Intelligent upload scheduling to avoid Instagram limits
- **Error Recovery**: Robust error handling with retry logic
- **Logging & Monitoring**: Comprehensive logging with optional Prometheus/Grafana integration

## 🏗️ Architecture

```
shared/
├── user1/
│   ├── videos/     # Drop videos here
│   └── images/     # Drop images here
├── user2/
│   ├── videos/
│   └── images/
└── ...

processed/
├── user1/
│   ├── videos/     # Successfully processed videos
│   ├── images/     # Successfully processed images
│   ├── queue/      # Processing queue
│   └── failed/     # Failed uploads with error logs
└── ...
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Instagram account credentials
- OpenAI API key
- Raspberry Pi 4 (2GB+ RAM recommended) or any Linux system

### 1. Clone and Setup

```bash
git clone https://github.com/your-username/instagram-content-generator.git
cd instagram-content-generator

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` file with your credentials:

```bash
# Instagram API Configuration
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password

# OpenAI API for caption generation
OPENAI_API_KEY=your_openai_api_key

# Optional: Customize settings
SCAN_INTERVAL_MINUTES=30
UPLOAD_DELAY_MINUTES=60
MAX_CAPTION_LENGTH=2200
```

### 3. Create Directory Structure

```bash
# Create shared directories for your users
mkdir -p shared/user1/{videos,images}
mkdir -p shared/user2/{videos,images}
mkdir -p processed logs temp data
```

### 4. Start the Service

```bash
# Start with Docker Compose
docker-compose up -d

# Or specify users explicitly
docker-compose run instagram-content-generator python -m instagram_content_generator.main run user1 user2
```

### 5. Add Content

Simply drop images or videos into the appropriate user folders:

```bash
# Add content for user1
cp /path/to/video.mp4 shared/user1/videos/
cp /path/to/image.jpg shared/user1/images/
```

The system will automatically:
1. Detect new files
2. Analyze content using AI
3. Generate engaging captions
4. Upload to Instagram
5. Move processed files to the `processed` directory

## 📋 Usage

### Command Line Interface

```bash
# Run continuous monitoring (recommended)
python -m instagram_content_generator.main run user1 user2 user3

# Run single scan without continuous monitoring
python -m instagram_content_generator.main scan user1

# Show system status
python -m instagram_content_generator.main status

# Show help
python -m instagram_content_generator.main --help
```

### Docker Commands

```bash
# Start service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop service
docker-compose down

# Health check
docker-compose exec instagram-content-generator /usr/local/bin/health_check.sh

# Shell access
docker-compose exec instagram-content-generator bash
```

### Health Monitoring

The service provides health check endpoints:

```bash
# Basic health check
curl http://localhost:8080/health

# Detailed metrics
curl http://localhost:8080/metrics

# Full status including system info
curl http://localhost:8080/status
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTAGRAM_USERNAME` | *required* | Instagram username for posting |
| `INSTAGRAM_PASSWORD` | *required* | Instagram password |
| `OPENAI_API_KEY` | *required* | OpenAI API key for caption generation |
| `SHARED_FOLDER_PATH` | `/shared` | Path to shared content folder |
| `PROCESSED_FOLDER_PATH` | `/processed` | Path to processed files |
| `SCAN_INTERVAL_MINUTES` | `30` | How often to scan for new files |
| `UPLOAD_DELAY_MINUTES` | `60` | Minimum delay between uploads |
| `MAX_CAPTION_LENGTH` | `2200` | Maximum Instagram caption length |
| `USE_HASHTAGS` | `true` | Whether to add hashtags |
| `MAX_HASHTAGS` | `30` | Maximum number of hashtags |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `HEALTH_CHECK_PORT` | `8080` | Port for health check endpoint |

### Content Analysis Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTENT_ANALYSIS_MODEL` | `openai/clip-vit-base-patch32` | Model for content classification |
| `CAPTION_GENERATION_MODEL` | `gpt-4` | OpenAI model for caption generation |
| `CAPTION_TEMPERATURE` | `0.7` | Creativity level for caption generation |

### Upload Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `UPLOAD_QUALITY` | `high` | Instagram upload quality |
| `VIDEO_MAX_SIZE_MB` | `100` | Maximum video file size |
| `IMAGE_MAX_SIZE_MB` | `8` | Maximum image file size |

## 🔧 Advanced Usage

### Multiple Instagram Accounts

To manage multiple Instagram accounts, you'll need separate credential sets. The current version uses a single Instagram account for all users. For true multi-account support, extend the configuration to include per-user credentials.

### Custom Caption Styles

Modify the caption generation by adjusting the `style` parameter in the code:

- `engaging`: Default, friendly and interactive
- `professional`: Business-focused content
- `casual`: Relaxed, conversational tone
- `funny`: Humorous content

### Monitoring with Prometheus/Grafana

Enable monitoring stack:

```bash
# Start with monitoring
docker-compose --profile monitoring up -d

# Access Grafana at http://localhost:3000
# Default credentials: admin/admin
```

### Custom Content Analysis

The system supports various content categories:
- Gaming, Sports, Food, Travel, Fashion
- Technology, Nature, Lifestyle, Fitness
- Art, Music, Education, Business, etc.

## 🛠️ Development

### Local Development Setup

```bash
# Install uv for package management
pip install uv

# Create virtual environment
uv venv venv
source venv/bin/activate  # Linux/Mac
# or venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -r pyproject.toml

# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
isort src/

# Type checking
mypy src/
```

### Project Structure

```
src/
└── instagram_content_generator/
    ├── main.py                 # Main entry point
    └── modules/
        ├── config_manager.py   # Configuration management
        ├── content_analyzer.py # AI content analysis
        ├── caption_generator.py # Caption generation
        ├── instagram_uploader.py # Instagram API integration
        ├── video_scanner.py    # File monitoring and scanning
        ├── scheduler.py        # Main automation scheduler
        └── monitoring.py       # Health checks and monitoring
```

### Adding New Features

1. **Content Analysis**: Extend `ContentAnalyzer` class in `content_analyzer.py`
2. **Caption Generation**: Modify `CaptionGenerator` class in `caption_generator.py`
3. **File Processing**: Update `FileScanner` in `video_scanner.py`
4. **Scheduling**: Extend `InstagramScheduler` in `scheduler.py`

## 🐛 Troubleshooting

### Common Issues

1. **Instagram Authentication Fails**
   ```bash
   # Check credentials in .env file
   # Ensure two-factor authentication is disabled
   # Try logging in manually first
   ```

2. **Files Not Being Processed**
   ```bash
   # Check file permissions
   chmod -R 755 shared/
   
   # Check logs
   docker-compose logs -f
   
   # Verify file formats are supported
   ```

3. **High Memory Usage**
   ```bash
   # Reduce concurrent processing
   # Use smaller AI models
   # Increase swap space on Raspberry Pi
   ```

4. **Upload Failures**
   ```bash
   # Check Instagram rate limits
   # Verify content meets Instagram guidelines
   # Check network connectivity
   ```

### Debug Commands

```bash
# Check health status
curl http://localhost:8080/health

# View detailed logs
docker-compose logs instagram-content-generator

# Check system resources
docker-compose exec instagram-content-generator /usr/local/bin/health_check.sh system

# Manual file processing
docker-compose exec instagram-content-generator python -m instagram_content_generator.main scan user1
```

### Log Files

- Main log: `/var/log/instagram-content-generator.log`
- Error log: `/var/log/errors.log`
- Structured log: `/var/log/structured.log`

## 📊 Monitoring

### Health Check Endpoints

- `GET /health` - Basic health status
- `GET /metrics` - Detailed metrics in JSON
- `GET /status` - Complete system status

### Key Metrics

- Processing statistics (processed, success, failed)
- System resources (CPU, memory, disk, temperature)
- Error rates and recent errors
- Queue status and sizes
- Uptime and last activity

### Alerts

Set up monitoring alerts for:
- Service health failures
- High error rates
- System resource exhaustion
- Processing queue backup
- Upload failures

## 🔒 Security

### Best Practices

1. **Environment Variables**: Never commit credentials to version control
2. **File Permissions**: Restrict access to configuration files
3. **Network Security**: Use firewall rules for exposed ports
4. **Regular Updates**: Keep dependencies and base images updated
5. **Monitoring**: Monitor for unusual activity or errors

### Instagram Account Security

- Use application-specific passwords when possible
- Monitor account activity regularly
- Keep upload rates within reasonable limits
- Ensure content complies with Instagram guidelines

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

- 📧 Email: support@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/your-username/instagram-content-generator/issues)
- 📖 Documentation: [Wiki](https://github.com/your-username/instagram-content-generator/wiki)

## 🙏 Acknowledgments

- OpenAI for GPT models and API
- Hugging Face for computer vision models
- Instagram for the platform
- The open-source community for excellent libraries

---

**⚠️ Disclaimer**: This tool is for educational and personal use. Ensure compliance with Instagram's Terms of Service and API usage policies. Use responsibly and respect rate limits.