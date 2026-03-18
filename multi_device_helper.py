"""
Windows Multi-Device Audio Helper
Helps set up Windows to play audio to multiple devices simultaneously.
"""

import subprocess
import sys
import os


def enable_stereo_mix():
    """Instructions to enable Stereo Mix on Windows."""
    print("=" * 60)
    print("How to Enable Multi-Device Audio on Windows")
    print("=" * 60)
    print("\nMethod 1: Enable Stereo Mix (Recommended)")
    print("-" * 60)
    print("1. Right-click the speaker icon in your system tray")
    print("2. Select 'Sounds' or 'Sound settings'")
    print("3. Go to the 'Recording' tab")
    print("4. Right-click in an empty area and check 'Show Disabled Devices'")
    print("5. Find 'Stereo Mix' and right-click it")
    print("6. Select 'Enable'")
    print("7. Right-click 'Stereo Mix' again and select 'Set as Default Device'")
    print("8. Go to 'Playback' tab and set your desired output device")
    print("\nNow audio will play to both devices!")
    
    input("\nPress Enter to open Sound settings...")
    
    # Open Windows Sound settings
    try:
        subprocess.run(['mmsys.cpl'], shell=True)
    except Exception as e:
        print(f"Could not open sound settings: {e}")
        print("Please open them manually from Control Panel > Sound")


def setup_audio_mirroring():
    """Instructions for audio mirroring."""
    print("\n" + "=" * 60)
    print("Method 2: Use Audio Mirroring")
    print("-" * 60)
    print("1. Open Windows Settings (Win + I)")
    print("2. Go to System > Sound")
    print("3. Under 'Advanced sound options', click 'App volume and device preferences'")
    print("4. Configure your apps to use different output devices")
    print("\nNote: This method allows per-app device selection.")


def main():
    """Main helper function."""
    if sys.platform != 'win32':
        print("This helper is for Windows only.")
        print("On other platforms, use your system's audio routing features.")
        return
    
    print("\nChoose an option:")
    print("1. Show instructions for Stereo Mix (opens Sound settings)")
    print("2. Show instructions for Audio Mirroring")
    print("3. Exit")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        enable_stereo_mix()
    elif choice == '2':
        setup_audio_mirroring()
    else:
        print("Exiting...")


if __name__ == "__main__":
    main()

