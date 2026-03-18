# Audio Player with SoundCloud Streaming

A Python application to play music from local files and SoundCloud. Supports multi-device playback and flexible search!

## Features

- 🎵 **Local File Playback** - Play MP3, WAV, OGG, FLAC, M4A files
- 🔊 **SoundCloud Integration** - Search and stream from SoundCloud
- 🔍 **Flexible Search** - Find songs even if you don't know the exact name!
- 🖥️ **Clean GUI** - Easy-to-use tabbed interface
- 📦 **Simple Setup** - Minimal dependencies
- 💡 **Multi-Device Support** - Play to multiple speakers simultaneously

## Requirements

- Python 3.7 or higher
- Windows, macOS, or Linux

### Dependencies
- `pygame` - Audio playback (required)
- `yt-dlp` - SoundCloud search and download (required for streaming)
- `soundcloud-lib` - SoundCloud API (optional, for downloading)
- `requests` - HTTP requests (for streaming)

## Installation

### 🚀 Quick Install (Recommended)

**Windows:**
```batch
install.bat
```

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

**Docker (Any Platform):**
```bash
start-vnc-simple.bat  # Windows
# OR
docker-compose -f docker-compose.vnc.yml up --build  # Any platform
```

### Manual Install

```bash
pip install -r requirements.txt
```

### 📚 More Installation Options

See `INSTALL_ANYWHERE.md` for:
- Standalone executable creation
- Docker setup
- Distribution methods
- Troubleshooting

This installs:
- `pygame` - Core audio playback
- `yt-dlp` - SoundCloud search and streaming (REQUIRED for search to work)
- `soundcloud-lib` - SoundCloud downloading (optional)
- `requests` - HTTP requests

**Important:** `yt-dlp` is required for SoundCloud search to work. If search doesn't work, make sure yt-dlp is installed:
```bash
pip install yt-dlp
```

Or use the provided batch file on Windows:
```bash
install_ytdlp.bat
```

That's it! No API keys or complex setup needed.

## Quick Start

### 1. Run the Application

```bash
python audio_sync_gui.py
```

### 2. Play Local Files

1. Go to the "Local Files" tab
2. Click "Browse Audio File"
3. Select your music file
4. Click "Play"

### 3. Stream from SoundCloud

1. Go to the "SoundCloud" tab
2. Enter a search query (song name, artist, keywords - doesn't need to be exact!)
3. Click "Search" or press Enter
4. Double-click a track to play it

**The search is flexible!** You don't need the exact song name. Try:
- Partial song names: "bohemian" instead of "Bohemian Rhapsody"
- Artist names: "beatles" to find Beatles songs
- Keywords: "chill lofi" to find chill lofi music
- Any combination: "drake hotline" to find Drake's Hotline Bling

## Multi-Device Audio Setup

To play audio to multiple devices (computer + living room speakers):

### Method 1: Enable Stereo Mix (Easiest)

1. Right-click the speaker icon in your system tray
2. Select "Sounds" or "Sound settings"
3. Go to the "Recording" tab
4. Right-click in an empty area and check "Show Disabled Devices"
5. Find "Stereo Mix" and right-click it, then select "Enable"
6. Right-click "Stereo Mix" again and select "Properties"
7. Go to the "Listen" tab
8. Check "Listen to this device"
9. Select your second audio device from the dropdown
10. Click OK

Now audio will play to both devices simultaneously!

### Method 2: Use Third-Party Software

For easier multi-device audio, consider:
- **VoiceMeeter** (free) - Virtual audio mixer
- **Audio Router** (free) - Route audio to different devices
- **CheVolume** (paid) - Advanced audio routing

See the "Multi-Device Setup" tab in the GUI for detailed instructions.

## Usage

### GUI Version (Recommended)

```bash
python audio_sync_gui.py
```

The GUI has three tabs:
- **Local Files** - Browse and play local audio files
- **SoundCloud** - Search and stream music with flexible search
- **Multi-Device Setup** - Help for setting up multi-device audio

### Command-Line Version

```bash
python audio_sync_player.py
```

Enter the path to your audio file when prompted.

## How Flexible Search Works

The search engine is smart! It:

1. **Tries multiple query variations** - Removes common words, tries partial matches
2. **Searches broadly** - If you type "beatles", it finds songs by The Beatles
3. **Ranks by relevance** - Most relevant results appear first
4. **Works with partial info** - Just remember a few words? That's enough!

Examples:
- "that one song with the piano" → Finds piano-heavy tracks
- "drake" → Shows Drake songs
- "chill beats" → Finds chill music
- "summer vibes" → Finds summer-themed tracks

## Supported Audio Formats

- MP3
- WAV
- OGG
- FLAC
- M4A
- Any format supported by pygame

## Troubleshooting

### "No module named 'pygame'"

Install dependencies:
```bash
pip install -r requirements.txt
```

### SoundCloud search not working

**Most common issue:** `yt-dlp` is not installed or not in the correct Python environment.

1. **Check if yt-dlp is installed:**
   ```bash
   python -c "import yt_dlp; print('yt-dlp is installed')"
   ```

2. **If not installed, install it:**
   ```bash
   pip install yt-dlp
   ```
   
   Or on Windows, double-click `install_ytdlp.bat`

3. **If you're using a virtual environment or Anaconda:**
   - Make sure you're installing in the same environment where you run the GUI
   - Check which Python the GUI uses (shown in error messages)
   - Install using that Python: `path/to/python.exe -m pip install yt-dlp`

4. **After installing, restart the application**

5. **Optional:** Make sure `soundcloud-lib` is also installed:
   ```bash
   pip install soundcloud-lib
   ```

2. Check your internet connection

3. Some tracks may be region-restricted or unavailable

4. Try different search terms if results are limited

### Audio not playing

- Check that your audio file is a supported format
- Ensure your default audio device is working
- Try a different audio file

### Multi-device not working

- Make sure you've enabled Stereo Mix (see instructions above)
- Check that both devices are connected and recognized by Windows
- Try the setup helper: `python multi_device_helper.py`

### Search not finding songs

- Try different keywords or partial song names
- Search is flexible - you don't need exact matches
- Try searching by artist name if song name doesn't work
- Use fewer words for broader results

## Technical Details

- **Core Library**: pygame
- **Audio Engine**: pygame.mixer
- **SoundCloud**: soundcloud-lib
- **Search**: Flexible matching with relevance ranking
- **Multi-Device**: Uses Windows audio routing (Stereo Mix)

## Legal Notice

- Only download and play music you have the right to access
- Respect copyright and terms of service
- This tool is for personal use only

## Testing

Run tests to verify the search functionality:

```bash
# Quick test
python test_quick.py

# Full test suite
python test_streaming.py
```

See [TESTING.md](TESTING.md) for detailed testing information.

## Distribution

To create a distribution package for sharing:

1. **Quick Build (Windows)**:
   ```batch
   build_distribution.bat
   ```
   This creates a standalone executable in `dist\BluetoothStreamer\`

2. **Create Installer**:
   - Install [Inno Setup](https://jrsoftware.org/isinfo.php)
   - Open `create_installer.iss` and compile
   - Creates a Windows installer in `installer\`

See [DISTRIBUTION.md](DISTRIBUTION.md) for detailed distribution instructions.

## License

MIT License - see [LICENSE](LICENSE) file for details.
