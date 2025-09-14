# Multi-stage build for Instagram Content Generator
# Optimized for Raspberry Pi (ARM64)

# Build stage
FROM python:3.11.10-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    pkg-config \
    libssl-dev \
    libffi-dev \
    libmagic1 \
    libmagic-dev \
    libopencv-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy dependency files and source code
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies with uv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -e .

# Production stage
FROM python:3.11.10-slim as production

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libopencv-core4.5 \
    libopencv-imgproc4.5 \
    libopencv-imgcodecs4.5 \
    libopencv-videoio4.5 \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgtk-3-0 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create required directories
RUN mkdir -p /shared /processed /var/log /app/temp \
    && chown -R appuser:appuser /app /shared /processed /var/log

# Health check script
COPY scripts/health_check.sh /usr/local/bin/health_check.sh
RUN chmod +x /usr/local/bin/health_check.sh

# Setup health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /usr/local/bin/health_check.sh

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV HEALTH_CHECK_ENABLED=true
ENV HEALTH_CHECK_PORT=8080

# Expose health check port
EXPOSE 8080

# Volume mounts for data persistence
VOLUME ["/shared", "/processed", "/var/log"]

# Default command
CMD ["python", "-m", "src.main", "run"]