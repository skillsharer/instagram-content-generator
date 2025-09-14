#!/bin/bash

# Setup script for Instagram Content Generator
# This script helps with initial setup and deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="Instagram Content Generator"
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"
ENV_EXAMPLE=".env.example"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SETUP]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    print_header "Checking prerequisites..."
    
    local missing_deps=0
    
    # Check Docker
    if command_exists docker; then
        print_status "Docker found: $(docker --version)"
    else
        print_error "Docker not found. Please install Docker first."
        echo "  Ubuntu/Debian: sudo apt-get install docker.io"
        echo "  CentOS/RHEL: sudo yum install docker"
        echo "  macOS: Download from https://docker.com"
        missing_deps=$((missing_deps + 1))
    fi
    
    # Check Docker Compose
    if command_exists docker-compose; then
        print_status "Docker Compose found: $(docker-compose --version)"
    elif docker compose version >/dev/null 2>&1; then
        print_status "Docker Compose (plugin) found: $(docker compose version)"
    else
        print_error "Docker Compose not found. Please install Docker Compose."
        echo "  See: https://docs.docker.com/compose/install/"
        missing_deps=$((missing_deps + 1))
    fi
    
    # Check if running as root (not recommended)
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root is not recommended for security reasons."
        print_warning "Consider creating a dedicated user for this application."
    fi
    
    # Check available disk space
    local available_space
    available_space=$(df . | tail -1 | awk '{print $4}')
    local available_gb=$((available_space / 1024 / 1024))
    
    if [ "$available_gb" -lt 5 ]; then
        print_error "Insufficient disk space. At least 5GB required, found ${available_gb}GB"
        missing_deps=$((missing_deps + 1))
    else
        print_status "Disk space: ${available_gb}GB available"
    fi
    
    # Check memory (important for Raspberry Pi)
    if [ -f /proc/meminfo ]; then
        local total_mem
        total_mem=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        local total_mem_gb=$((total_mem / 1024 / 1024))
        
        if [ "$total_mem_gb" -lt 2 ]; then
            print_warning "Low memory detected: ${total_mem_gb}GB. Performance may be limited."
            print_warning "Consider enabling swap or using a device with more RAM."
        else
            print_status "Memory: ${total_mem_gb}GB available"
        fi
    fi
    
    return $missing_deps
}

# Function to setup environment file
setup_environment() {
    print_header "Setting up environment configuration..."
    
    if [ -f "$ENV_FILE" ]; then
        print_warning "Environment file already exists: $ENV_FILE"
        echo -n "Do you want to overwrite it? [y/N]: "
        read -r response
        if [[ ! "$response" =~ ^[Yy]$ ]]; then
            print_status "Keeping existing environment file"
            return 0
        fi
    fi
    
    if [ ! -f "$ENV_EXAMPLE" ]; then
        print_error "Environment example file not found: $ENV_EXAMPLE"
        return 1
    fi
    
    # Copy example file
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    print_status "Created environment file: $ENV_FILE"
    
    # Interactive configuration
    echo ""
    echo "Please provide the following configuration values:"
    echo "(Press Enter to keep default values in brackets)"
    echo ""
    
    # Instagram credentials
    echo -n "Instagram Username: "
    read -r instagram_username
    if [ -n "$instagram_username" ]; then
        sed -i "s/your_instagram_username/$instagram_username/" "$ENV_FILE"
    fi
    
    echo -n "Instagram Password: "
    read -rs instagram_password
    echo ""
    if [ -n "$instagram_password" ]; then
        sed -i "s/your_instagram_password/$instagram_password/" "$ENV_FILE"
    fi
    
    # OpenAI API key
    echo -n "OpenAI API Key: "
    read -rs openai_api_key
    echo ""
    if [ -n "$openai_api_key" ]; then
        sed -i "s/your_openai_api_key/$openai_api_key/" "$ENV_FILE"
    fi
    
    # Optional settings
    echo ""
    echo "Optional settings (press Enter for defaults):"
    
    echo -n "Scan interval in minutes [30]: "
    read -r scan_interval
    if [ -n "$scan_interval" ]; then
        sed -i "s/SCAN_INTERVAL_MINUTES=30/SCAN_INTERVAL_MINUTES=$scan_interval/" "$ENV_FILE"
    fi
    
    echo -n "Upload delay in minutes [60]: "
    read -r upload_delay
    if [ -n "$upload_delay" ]; then
        sed -i "s/UPLOAD_DELAY_MINUTES=60/UPLOAD_DELAY_MINUTES=$upload_delay/" "$ENV_FILE"
    fi
    
    print_status "Environment configuration completed"
    
    # Secure the environment file
    chmod 600 "$ENV_FILE"
    print_status "Set secure permissions on $ENV_FILE"
}

# Function to create directory structure
create_directories() {
    print_header "Creating directory structure..."
    
    local dirs=(
        "shared"
        "processed"
        "logs"
        "temp"
        "data"
        "monitoring"
    )
    
    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
            print_status "Created directory: $dir"
        else
            print_status "Directory exists: $dir"
        fi
    done
    
    # Set proper permissions
    chmod 755 shared processed logs temp data
    
    # Create example user directories
    echo ""
    echo -n "Create example user directories? [Y/n]: "
    read -r response
    if [[ ! "$response" =~ ^[Nn]$ ]]; then
        mkdir -p shared/user1/{videos,images}
        mkdir -p shared/user2/{videos,images}
        print_status "Created example user directories: user1, user2"
        
        # Create README files
        cat > shared/README.md << EOF
# Shared Content Directory

This directory contains content files organized by Instagram username.

Structure:
- \`<username>/videos/\` - Drop video files here for automatic processing
- \`<username>/images/\` - Drop image files here for automatic processing

Supported formats:
- Images: JPG, PNG, GIF, BMP, WebP
- Videos: MP4, AVI, MOV, MKV, WMV, FLV, WebM

The system will automatically:
1. Detect new files
2. Analyze content using AI
3. Generate engaging captions
4. Upload to Instagram
5. Move processed files to the processed directory
EOF
        
        cat > shared/user1/README.md << EOF
# User1 Content Directory

Drop your content files here:
- \`videos/\` - Video content for Instagram posts
- \`images/\` - Image content for Instagram posts

Files will be automatically processed and uploaded to Instagram.
EOF
        
        cp shared/user1/README.md shared/user2/README.md
        sed -i 's/User1/User2/' shared/user2/README.md
    fi
}

# Function to setup systemd service (Linux only)
setup_systemd_service() {
    if [[ "$OSTYPE" != "linux-gnu"* ]]; then
        print_warning "Systemd service setup only available on Linux"
        return 0
    fi
    
    print_header "Setting up systemd service..."
    
    echo -n "Setup systemd service for auto-start? [y/N]: "
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        return 0
    fi
    
    local service_file="/etc/systemd/system/instagram-content-generator.service"
    local current_dir
    current_dir=$(pwd)
    
    if [ ! -f "scripts/instagram-content-generator.service" ]; then
        print_error "Service file template not found"
        return 1
    fi
    
    # Create service file
    sudo cp "scripts/instagram-content-generator.service" "$service_file"
    sudo sed -i "s|/path/to/instagram-content-generator|$current_dir|g" "$service_file"
    sudo sed -i "s|User=pi|User=$USER|g" "$service_file"
    sudo sed -i "s|Group=pi|Group=$USER|g" "$service_file"
    
    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable instagram-content-generator.service
    
    print_status "Systemd service created and enabled"
    print_status "Use 'sudo systemctl start instagram-content-generator' to start"
    print_status "Use 'sudo systemctl status instagram-content-generator' to check status"
}

# Function to build Docker images
build_docker_images() {
    print_header "Building Docker images..."
    
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        print_error "Docker Compose file not found: $DOCKER_COMPOSE_FILE"
        return 1
    fi
    
    print_status "Building images (this may take a while)..."
    
    if command_exists docker-compose; then
        docker-compose build
    else
        docker compose build
    fi
    
    print_status "Docker images built successfully"
}

# Function to test the setup
test_setup() {
    print_header "Testing the setup..."
    
    # Check if environment file is properly configured
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Environment file not found: $ENV_FILE"
        return 1
    fi
    
    # Check for required environment variables
    local missing_vars=0
    
    if ! grep -q "INSTAGRAM_USERNAME=.*[^=]" "$ENV_FILE"; then
        print_error "Instagram username not configured"
        missing_vars=$((missing_vars + 1))
    fi
    
    if ! grep -q "INSTAGRAM_PASSWORD=.*[^=]" "$ENV_FILE"; then
        print_error "Instagram password not configured"
        missing_vars=$((missing_vars + 1))
    fi
    
    if ! grep -q "OPENAI_API_KEY=.*[^=]" "$ENV_FILE"; then
        print_error "OpenAI API key not configured"
        missing_vars=$((missing_vars + 1))
    fi
    
    if [ $missing_vars -gt 0 ]; then
        print_error "Please configure missing environment variables in $ENV_FILE"
        return 1
    fi
    
    # Test Docker Compose configuration
    print_status "Validating Docker Compose configuration..."
    
    if command_exists docker-compose; then
        docker-compose config >/dev/null
    else
        docker compose config >/dev/null
    fi
    
    print_status "Docker Compose configuration is valid"
    
    # Test health check script
    if [ -f "scripts/health_check.sh" ]; then
        chmod +x scripts/health_check.sh
        print_status "Health check script is executable"
    fi
    
    print_status "Setup validation completed successfully"
}

# Function to show usage instructions
show_usage_instructions() {
    print_header "Setup completed! Next steps:"
    
    echo ""
    echo "1. Start the service:"
    echo "   docker-compose up -d"
    echo ""
    echo "2. Check the logs:"
    echo "   docker-compose logs -f"
    echo ""
    echo "3. Add content to process:"
    echo "   cp your-image.jpg shared/user1/images/"
    echo "   cp your-video.mp4 shared/user1/videos/"
    echo ""
    echo "4. Monitor health:"
    echo "   curl http://localhost:8080/health"
    echo ""
    echo "5. Check status:"
    echo "   docker-compose exec instagram-content-generator python -m instagram_content_generator.main status"
    echo ""
    echo "For more information, see README.md"
    echo ""
    
    if [[ "$OSTYPE" == "linux-gnu"* ]] && systemctl is-enabled instagram-content-generator.service >/dev/null 2>&1; then
        echo "Systemd service is enabled. The service will start automatically on boot."
        echo "To start now: sudo systemctl start instagram-content-generator"
        echo ""
    fi
}

# Main setup function
main() {
    echo ""
    echo "========================================"
    echo "  $PROJECT_NAME Setup"
    echo "========================================"
    echo ""
    
    # Check prerequisites
    if ! check_prerequisites; then
        print_error "Prerequisites check failed. Please resolve the issues above."
        exit 1
    fi
    
    echo ""
    
    # Setup environment
    setup_environment
    
    echo ""
    
    # Create directories
    create_directories
    
    echo ""
    
    # Build Docker images
    build_docker_images
    
    echo ""
    
    # Setup systemd service (optional)
    setup_systemd_service
    
    echo ""
    
    # Test setup
    test_setup
    
    echo ""
    
    # Show usage instructions
    show_usage_instructions
    
    print_status "Setup completed successfully!"
}

# Handle command line arguments
case "${1:-setup}" in
    setup)
        main
        ;;
    env|environment)
        setup_environment
        ;;
    dirs|directories)
        create_directories
        ;;
    build)
        build_docker_images
        ;;
    test)
        test_setup
        ;;
    systemd)
        setup_systemd_service
        ;;
    --help|-h)
        echo "Usage: $0 [setup|env|dirs|build|test|systemd]"
        echo ""
        echo "Commands:"
        echo "  setup     - Full setup (default)"
        echo "  env       - Setup environment configuration only"
        echo "  dirs      - Create directory structure only"
        echo "  build     - Build Docker images only"
        echo "  test      - Test the setup only"
        echo "  systemd   - Setup systemd service only"
        echo ""
        exit 0
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac