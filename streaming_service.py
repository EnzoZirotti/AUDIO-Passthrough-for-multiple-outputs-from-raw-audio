"""
SoundCloud Streaming Service (Backward Compatibility Module)
This module provides backward compatibility for existing imports.
New code should import from bluetoothstreamer.streaming instead.
"""

# Import from new modules for backward compatibility
from bluetoothstreamer.streaming.soundcloud_service import SoundCloudService
from bluetoothstreamer.streaming.streaming_manager import StreamingManager

# Re-export for backward compatibility
__all__ = ['SoundCloudService', 'StreamingManager']
