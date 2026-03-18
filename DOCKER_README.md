# Docker Setup for Audio Sync GUI

This guide explains how to run the Audio Sync GUI application using Docker.

## Prerequisites

- Docker installed on your system
- Docker Compose (usually included with Docker Desktop)

## Quick Start

### Windows

1. **Build the Docker image**:
   ```batch
   docker-build.bat
   ```

2. **Run the application**:
   ```batch
   docker-run.bat
   ```
   
   Or use Docker Compose:
   ```batch
   docker-compose up
   ```

### Linux (Recommended)

1. **Make the run script executable** (one-time):
   ```bash
   chmod +x docker-run.sh
   ```

2. **Allow X11 forwarding** (one-time setup):
   ```bash
   xhost +local:docker
   ```

3. **Build and run**:
   ```bash
   # Build the image
   docker build -t audio-sync-gui .

   # Run using the helper script
   ./docker-run.sh
   ```
   
   Or use Docker Compose:
   ```bash
   docker-compose up --build
   ```

### macOS

On macOS, GUI forwarding requires XQuartz:

#### Option 1: Use WSL2 with X11 Server

1. Install WSL2 and an X11 server (like VcXsrv or X410)
2. Start your X11 server
3. In WSL2, set `DISPLAY`:
   ```bash
   export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
   ```
4. Run the Docker commands as shown in the Linux section

#### Option 2: Use VNC (Recommended for Windows)

We can modify the Dockerfile to include a VNC server. This allows you to access the GUI via a web browser or VNC client.

1. Install XQuartz:
   ```bash
   brew install --cask xquartz
   ```

2. Start XQuartz and allow connections:
   ```bash
   xhost +localhost
   ```

3. Build and run:
   ```bash
   docker build -t audio-sync-gui .
   docker run -it --rm \
     -e DISPLAY=host.docker.internal:0 \
     -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
     audio-sync-gui
   ```

## Building the Image

### Windows
```batch
docker-build.bat
```

### Linux/macOS
```bash
docker build -t audio-sync-gui .
```

## Running the Container

### Basic Run
```bash
docker run -it --rm audio-sync-gui
```

### With Audio Files Mounted
```bash
docker run -it --rm \
  -v /path/to/your/audio/files:/app/audio_files:ro \
  audio-sync-gui
```

### With Custom Display
```bash
docker run -it --rm \
  -e DISPLAY=:0 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  audio-sync-gui
```

## Troubleshooting

### GUI Not Showing

- **Linux**: Make sure you've run `xhost +local:docker`
- **Windows**: Use WSL2 with X11 server or VNC option
- **macOS**: Make sure XQuartz is running and connections are allowed

### Audio Not Working

- The container needs access to audio devices (`/dev/snd`)
- On Linux, you may need to run with `--privileged` flag
- Check that your audio devices are accessible: `ls -la /dev/snd`

### Permission Errors

- Try running with `--privileged` flag for full device access
- Or add your user to the `audio` group on Linux

## Notes

- Windows-specific dependencies (`pycaw`, `comtypes`, `PyAudioWPatch`) are not installed in the Linux container
- The application will work but some Windows-specific features may not be available
- Audio device access requires appropriate permissions
- On Windows, using WSL2 with X11 server is recommended for best GUI experience

## Windows-Specific Setup

For Windows users, GUI forwarding can be challenging. Here are your options:

### Option 1: Use WSL2 with X11 Server (Recommended)

1. Install WSL2 and an X11 server (like VcXsrv or X410)
2. Start your X11 server
3. In WSL2, set `DISPLAY`:
   ```bash
   export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):0.0
   ```
4. Run the Docker commands as shown in the Linux section

### Option 2: Use Docker Desktop with WSL2 Backend

1. Enable WSL2 backend in Docker Desktop settings
2. Use the Linux instructions within WSL2

## Alternative: VNC Setup

If you want to use VNC instead of X11 forwarding (better for Windows/remote access), we can modify the Dockerfile to include a VNC server. This would allow you to access the GUI via a web browser or VNC client. Let me know if you'd like this option!
