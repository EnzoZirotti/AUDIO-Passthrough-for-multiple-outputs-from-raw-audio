# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for audio, GUI, and other requirements
RUN apt-get update && apt-get install -y \
    # Audio libraries
    libasound2-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    # GUI dependencies (tkinter)
    python3-tk \
    # X11 for GUI forwarding
    x11-apps \
    xauth \
    # Build tools for some Python packages
    build-essential \
    gcc \
    g++ \
    # Network tools
    wget \
    curl \
    # Cleanup
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# Note: pycaw and comtypes are Windows-specific, so we'll skip them in Linux
# PyAudioWPatch is also Windows-specific, so we use pyaudio for Linux
RUN pip install --no-cache-dir \
    pygame>=2.5.0 \
    sounddevice>=0.4.6 \
    numpy>=1.24.0 \
    pydub>=0.25.1 \
    yt-dlp>=2023.12.30 \
    soundcloud-lib>=0.5.3 \
    requests>=2.31.0 \
    pyaudio

# Copy application files
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:0

# Expose any ports if needed (adjust based on your app's needs)
# EXPOSE 8080

# Run the GUI application
CMD ["python", "audio_sync_gui.py"]
