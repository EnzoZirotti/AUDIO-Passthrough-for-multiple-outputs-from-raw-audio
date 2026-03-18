#!/bin/bash
# Docker run script for Audio Sync GUI
# This script simplifies running the Docker container

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Audio Sync GUI - Docker Runner${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Detected: Linux"
    # Allow X11 forwarding
    xhost +local:docker 2>/dev/null || echo -e "${YELLOW}Warning: Could not set xhost. GUI may not work.${NC}"
    
    # Run with Linux-specific settings
    docker run -it --rm \
        -e DISPLAY=$DISPLAY \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
        -v /dev/snd:/dev/snd:rw \
        --privileged \
        --name audio-sync-gui \
        audio-sync-gui:latest

elif [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected: macOS"
    echo -e "${YELLOW}Make sure XQuartz is installed and running!${NC}"
    
    docker run -it --rm \
        -e DISPLAY=host.docker.internal:0 \
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
        --name audio-sync-gui \
        audio-sync-gui:latest

else
    echo "Detected: Windows or other"
    echo -e "${YELLOW}For Windows, please use WSL2 or Docker Desktop with proper X11 server setup.${NC}"
    echo "Or use docker-compose: docker-compose up"
    exit 1
fi
