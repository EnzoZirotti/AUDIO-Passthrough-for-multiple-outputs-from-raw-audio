"""
Synchronized Multi-Device Audio Player
Supports selecting specific audio output devices (Bluetooth, local audio, etc.)
"""

import pygame
import threading
import time
import os
from typing import List, Optional, Tuple, Dict

# Import structured logging
try:
    from audio_logger import get_logger
    logger = get_logger("AudioPlayer")
except ImportError:
    # Fallback to basic logging if audio_logger not available
    import logging
    logger = logging.getLogger("AudioPlayer")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

# Try to import sounddevice for device selection
# We'll check availability dynamically
SOUNDDEVICE_AVAILABLE = None
sd = None
np = None
AudioSegment = None

def _check_sounddevice():
    """Check if sounddevice is available (dynamic check)."""
    global SOUNDDEVICE_AVAILABLE, sd, np, AudioSegment
    if SOUNDDEVICE_AVAILABLE is None:
        try:
            import sounddevice as sd
            import numpy as np
            SOUNDDEVICE_AVAILABLE = True
            # Try to import pydub (optional, only needed for playback)
            try:
                from pydub import AudioSegment
            except ImportError:
                logger.warning("pydub not installed. Device enumeration will work, but playback may require pydub.")
                AudioSegment = None
        except ImportError as e:
            logger.warning(f"sounddevice or numpy not available: {e}")
            SOUNDDEVICE_AVAILABLE = False
    return SOUNDDEVICE_AVAILABLE


class SynchronizedAudioPlayer:
    """Plays audio with device selection support."""
    
    def __init__(self, device1: Optional[int] = None, device2: Optional[int] = None,
                 device1_latency_adjustment: float = 0.0, device2_latency_adjustment: float = 0.0):
        """
        Initialize the audio player.
        
        Args:
            device1: Index of first output device (None = default)
            device2: Index of second output device (None = no second device)
            device1_latency_adjustment: Manual latency adjustment for device 1 in seconds (can be negative)
            device2_latency_adjustment: Manual latency adjustment for device 2 in seconds (can be negative)
        """
        # Thread-safe state management
        self._state_lock = threading.RLock()  # Reentrant lock for state access
        self._is_playing = False
        self._is_paused = False
        
        self.audio_file = None
        self.device1 = device1
        self.device2 = device2
        self.device1_latency_adjustment = device1_latency_adjustment  # Manual adjustment in seconds
        self.device2_latency_adjustment = device2_latency_adjustment  # Manual adjustment in seconds
        self.play_threads = []
        
        # Consolidated stream management - single source of truth
        self._streams_lock = threading.Lock()  # Lock for stream registry
        self._active_streams = {}  # device_num -> stream mapping
        
        # Volume control with thread-safe access
        self._volume_lock = threading.Lock()
        self._volume1 = 1.0  # Volume for device 1 (0.0 to 1.0)
        self._volume2 = 1.0  # Volume for device 2 (0.0 to 1.0)
        
        self.pause_event = threading.Event()  # Event to control pause/resume
        self.original_samples = None  # Store original samples for volume adjustment
        self.sample_rate = None  # Store sample rate
        self.current_position = [0, 0]  # Track current playback position for each device
        self.device_latencies = {}  # Cache for device latency measurements
        
        # Initialize pygame as fallback
        pygame.mixer.init()
    
    @property
    def is_playing(self) -> bool:
        """Thread-safe access to playing state."""
        with self._state_lock:
            return self._is_playing
    
    @is_playing.setter
    def is_playing(self, value: bool):
        """Thread-safe setting of playing state."""
        with self._state_lock:
            self._is_playing = value
    
    @property
    def is_paused(self) -> bool:
        """Thread-safe access to paused state."""
        with self._state_lock:
            return self._is_paused
    
    @is_paused.setter
    def is_paused(self, value: bool):
        """Thread-safe setting of paused state."""
        with self._state_lock:
            self._is_paused = value
    
    def get_volume(self, device: int) -> float:
        """
        Get current volume for a device (thread-safe).
        
        Args:
            device: 1 for device1, 2 for device2
            
        Returns:
            Volume level (0.0 to 1.0)
        """
        with self._volume_lock:
            if device == 1:
                return self._volume1
            elif device == 2:
                return self._volume2
            return 1.0
    
    def set_volume(self, device: int, volume: float):
        """
        Set volume for a device (thread-safe). Volume changes take effect immediately during playback.
        
        Args:
            device: 1 for device1, 2 for device2
            volume: Volume level (0.0 to 1.0)
        """
        volume = max(0.0, min(1.0, volume))  # Clamp between 0 and 1
        
        with self._volume_lock:
            if device == 1:
                self._volume1 = volume
                # Update pygame volume if using it
                if not _check_sounddevice() or (self.device1 is None and self.device2 is None):
                    try:
                        pygame.mixer.music.set_volume(volume)
                    except:
                        pass
            elif device == 2:
                self._volume2 = volume
        
        print(f"Device {device} volume set to {volume*100:.1f}%")
    
    def _register_stream(self, device_num: int, stream):
        """Register an active stream (thread-safe)."""
        with self._streams_lock:
            self._active_streams[device_num] = stream
    
    def _unregister_stream(self, device_num: int):
        """Unregister a stream (thread-safe)."""
        with self._streams_lock:
            self._active_streams.pop(device_num, None)
    
    def _get_all_streams(self) -> dict:
        """Get copy of all active streams (thread-safe)."""
        with self._streams_lock:
            return dict(self._active_streams)
    
    def _close_all_streams(self):
        """Close all registered streams (thread-safe)."""
        streams_to_close = self._get_all_streams()
        with self._streams_lock:
            self._active_streams.clear()
        
        for device_num, stream in streams_to_close.items():
            try:
                if stream is not None:
                    if hasattr(stream, 'stop'):
                        stream.stop()
                    if hasattr(stream, 'close'):
                        stream.close()
            except Exception as e:
                print(f"Error closing stream for device {device_num}: {e}")
        
    @staticmethod
    def get_audio_devices() -> List[Dict]:
        """Get list of available audio output devices."""
        devices = []
        
        print("Checking sounddevice availability...")
        is_available = _check_sounddevice()
        print(f"sounddevice available: {is_available}")
        
        # Check if sounddevice is available (dynamic check)
        if is_available:
            try:
                print("Querying audio devices...")
                all_devices = sd.query_devices()
                print(f"Found {len(all_devices)} total devices from sounddevice")
                
                # Use a dict to track unique devices by base name, preferring longer/more complete names and 44100 Hz
                # Key: normalized base name, Value: device info with longest name
                device_map = {}
                
                def get_base_name(name):
                    """Extract base name for grouping similar devices."""
                    # Remove common suffixes and get the main part
                    name = name.strip()
                    # Try to get the part before the first incomplete parenthesis
                    # or use the full name if it looks complete
                    if '(' in name:
                        # Check if it ends with ) - if not, might be truncated
                        if not name.endswith(')'):
                            # Might be truncated, extract base before last incomplete part
                            # Count open and close parens
                            open_count = name.count('(')
                            close_count = name.count(')')
                            if open_count > close_count:
                                # Incomplete, try to get a base name
                                # Find the last complete parenthetical group
                                last_close = name.rfind(')')
                                if last_close > 0:
                                    # Has at least one complete group, use everything up to that
                                    base = name[:last_close + 1]
                                    return base
                                else:
                                    # No complete groups, use part before first (
                                    return name.split('(')[0].strip()
                    return name
                
                def names_are_similar(name1, name2):
                    """Check if two device names refer to the same device."""
                    name1 = name1.strip().lower()
                    name2 = name2.strip().lower()
                    
                    # Exact match
                    if name1 == name2:
                        return True
                    
                    # Check if one is a prefix of the other (truncation case)
                    if name1.startswith(name2) or name2.startswith(name1):
                        # But make sure the difference isn't too large (avoid false matches)
                        len_diff = abs(len(name1) - len(name2))
                        if len_diff < 20:  # Reasonable truncation length
                            return True
                    
                    # Check base names (before parentheses)
                    base1 = name1.split('(')[0].strip()
                    base2 = name2.split('(')[0].strip()
                    if base1 and base2 and base1 == base2:
                        # Same base, check if one looks like a truncated version
                        # If one is much shorter and the other contains it, likely same device
                        if len(name1) < len(name2) and name1 in name2:
                            return True
                        if len(name2) < len(name1) and name2 in name1:
                            return True
                    
                    return False
                
                for i, device in enumerate(all_devices):
                    if device['max_output_channels'] > 0:  # Output device
                        device_name = device['name'].strip()
                        if not device_name:
                            continue
                        
                        sample_rate = int(device['default_samplerate'])
                        
                        # Check if this device matches an existing one
                        matched_key = None
                        for key, existing_dev in device_map.items():
                            if names_are_similar(device_name, existing_dev['name']):
                                matched_key = key
                                break
                        
                        if matched_key is None:
                            # New device, add it
                            # Use a normalized key based on base name
                            base_name = get_base_name(device_name)
                            normalized_base = base_name.lower().strip()
                            device_map[normalized_base] = {
                                'index': i,
                                'name': device_name,  # Keep the actual full name
                                'channels': device['max_output_channels'],
                                'sample_rate': sample_rate
                            }
                        else:
                            # We have a similar device, prefer the one with:
                            # 1. Longer name (more complete, not truncated)
                            # 2. 44100 Hz sample rate
                            existing = device_map[matched_key]
                            
                            should_replace = False
                            
                            # Check if current name is longer (more complete)
                            current_len = len(device_name)
                            existing_len = len(existing['name'])
                            
                            # Prefer longer name (indicates more complete information)
                            if current_len > existing_len:
                                should_replace = True
                            # If same length, check for truncation indicators
                            elif current_len == existing_len:
                                # Check if one looks more complete (has closing paren, etc.)
                                current_complete = device_name.endswith(')') or device_name.endswith('Device') or device_name.endswith('Speaker')
                                existing_complete = existing['name'].endswith(')') or existing['name'].endswith('Device') or existing['name'].endswith('Speaker')
                                
                                if current_complete and not existing_complete:
                                    should_replace = True
                                elif current_complete == existing_complete:
                                    # Both same completeness, prefer 44100 Hz
                                    if sample_rate == 44100 and existing['sample_rate'] != 44100:
                                        should_replace = True
                            # If existing is longer but current has 44100 Hz and existing doesn't
                            elif sample_rate == 44100 and existing['sample_rate'] != 44100:
                                # Only replace if the length difference is small (within 15 chars)
                                if existing_len - current_len <= 15:
                                    should_replace = True
                            
                            if should_replace:
                                # Update the existing entry
                                device_map[matched_key] = {
                                    'index': i,
                                    'name': device_name,
                                    'channels': device['max_output_channels'],
                                    'sample_rate': sample_rate
                                }
                
                # Convert to list, remove helper fields, and sort by name
                devices = []
                for dev in device_map.values():
                    devices.append({
                        'index': dev['index'],
                        'name': dev['name'],
                        'channels': dev['channels'],
                        'sample_rate': dev['sample_rate']
                    })
                devices.sort(key=lambda x: x['name'].lower())
                print(f"Found {len(devices)} unique output devices")
                
            except Exception as e:
                print(f"Error querying devices: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("sounddevice is not available - cannot enumerate devices")
        
        # If no devices found or sounddevice not available, add default
        if not devices:
            print("No devices found, adding default device")
            devices.append({
                'index': None,
                'name': 'Default Output Device',
                'channels': 2,
                'sample_rate': 44100
            })
        
        return devices
    
    @staticmethod
    def _is_bluetooth_device(device_name: str) -> bool:
        """
        Check if a device is a Bluetooth device based on its name.
        Uses strict detection to avoid false positives with wired headphones.
        """
        if not device_name:
            return False
        name_lower = device_name.lower()
        
        # STRICT Bluetooth indicators - only actual Bluetooth-specific terms
        # Removed generic terms like 'headset', 'earphone', 'wireless' that match wired devices
        bluetooth_indicators = [
            'bluetooth',           # Direct Bluetooth mention
            ' bt',                 # Space before BT
            'bt ',                 # BT followed by space
            'bth',                 # Bluetooth abbreviation
            'hands-free',          # Bluetooth hands-free profile
            'a2dp',                # Advanced Audio Distribution Profile (Bluetooth only)
            'bthhfenum',           # Windows Bluetooth Hands-Free driver
        ]
        
        # Bluetooth-specific brand/model names (ONLY if they're exclusively Bluetooth)
        bluetooth_only_brands = [
            'airpods',             # Apple AirPods (always Bluetooth)
            'galaxy buds',         # Samsung Galaxy Buds (always Bluetooth)
            'pixel buds',          # Google Pixel Buds (always Bluetooth)
            'tws',                 # True Wireless Stereo (Bluetooth only)
        ]
        
        # Check for strict Bluetooth indicators first
        if any(indicator in name_lower for indicator in bluetooth_indicators):
            return True
        
        # Check for Bluetooth-only brands (these are always Bluetooth)
        if any(brand in name_lower for brand in bluetooth_only_brands):
            return True
        
        # Check for Windows Bluetooth driver path (most reliable indicator)
        if 'bthhfenum' in name_lower or '@system32\\drivers\\bthhfenum' in name_lower:
            return True
        
        return False
    
    def _measure_device_latency(self, device_index: Optional[int], device_name: str, sample_rate: int = 44100, num_measurements: int = 3) -> float:
        """
        Measure actual latency of a device by creating test streams and measuring
        the time from stream.start() to when callbacks are invoked.
        Uses multiple measurements and statistical validation for accuracy.
        
        Args:
            device_index: Device index to measure
            device_name: Device name for logging
            sample_rate: Sample rate to use
            num_measurements: Number of measurements to take (default 3)
            
        Returns:
            Measured latency in seconds (median of measurements, or 0.0 if measurement fails)
        """
        if not _check_sounddevice():
            return 0.0
        
        if device_index is None:
            return 0.0
        
        measurements = []
        
        for attempt in range(num_measurements):
            try:
                callback_invoked = threading.Event()
                start_time = [None]
                
                def test_callback(outdata, frames, time_info, status):
                    """Callback to measure when audio actually starts processing."""
                    if start_time[0] is None:
                        start_time[0] = time.time()
                        callback_invoked.set()
                        raise sd.CallbackStop()  # Stop after first callback
                
                # Create a test stream
                stream = None
                try:
                    stream = sd.OutputStream(
                        samplerate=sample_rate,
                        channels=2,
                        device=device_index,
                        callback=test_callback,
                        dtype=np.float32,
                        blocksize=512  # Small block size for faster measurement
                    )
                    
                    # Measure latency
                    stream_start_time = time.time()
                    stream.start()
                    
                    # Wait for callback (with timeout)
                    if callback_invoked.wait(timeout=0.5):
                        if start_time[0] is not None:
                            measured_latency = start_time[0] - stream_start_time
                            if measured_latency > 0:
                                measurements.append(measured_latency)
                    else:
                        # Timeout - skip this measurement
                        pass
                        
                except Exception as e:
                    if attempt == 0:  # Only print error on first attempt
                        print(f"Error in latency measurement attempt {attempt + 1} for '{device_name}': {e}")
                finally:
                    # Always cleanup stream
                    if stream is not None:
                        try:
                            stream.stop()
                            stream.close()
                        except:
                            pass
                        time.sleep(0.01)  # Small delay to ensure stream is fully closed
                
                # Small delay between measurements
                if attempt < num_measurements - 1:
                    time.sleep(0.05)
                    
            except Exception as e:
                if attempt == 0:
                    print(f"Error in latency measurement for '{device_name}': {e}")
                continue
        
        # Calculate median latency (more robust than mean)
        if measurements:
            measurements.sort()
            median_latency = measurements[len(measurements) // 2]
            
            # Validate measurement consistency (remove outliers)
            if len(measurements) >= 3:
                # Remove measurements that are more than 2x the median
                filtered = [m for m in measurements if m <= median_latency * 2 and m >= median_latency * 0.5]
                if filtered:
                    filtered.sort()
                    median_latency = filtered[len(filtered) // 2]
            
            print(f"Latency measurement for '{device_name}': {median_latency*1000:.1f}ms (from {len(measurements)}/{num_measurements} successful measurements)")
            return max(0.0, median_latency)
        else:
            print(f"Latency measurement failed for '{device_name}' - no successful measurements")
            return 0.0
    
    def _get_device_latency(self, device_index: Optional[int], device_name: str, sample_rate: int = 44100, measure: bool = True) -> float:
        """
        Get latency compensation for a device in seconds.
        If measure=True, attempts to measure actual latency before using estimates.
        Returns latency in seconds (positive value).
        Manual adjustments are applied on top of measured/estimated latency.
        """
        if device_index is None:
            return 0.0
        
        # Get manual adjustment for this device (in seconds, can be negative)
        # Check if this device index matches device1 or device2
        manual_adjustment_seconds = None
        if self.device1 is not None and device_index == self.device1:
            manual_adjustment_seconds = self.device1_latency_adjustment
        elif self.device2 is not None and device_index == self.device2:
            manual_adjustment_seconds = self.device2_latency_adjustment
        
        # If user has manually adjusted (non-zero), treat it as a relative adjustment
        # Otherwise, measure/estimate base latency
        if manual_adjustment_seconds is not None and abs(manual_adjustment_seconds) > 0.0001:
            # User has manually adjusted - this is a RELATIVE adjustment
            # We still need the base latency to apply the adjustment to
            base_latency = 0.0
            if device_index in self.device_latencies:
                base_latency = self.device_latencies[device_index]
            else:
                # Need to measure or estimate base latency first
                latency = 0.0
                
                # Try to measure actual latency if requested
                if measure and _check_sounddevice():
                    print(f"Measuring latency for '{device_name}'...")
                    measured_latency = self._measure_device_latency(device_index, device_name, sample_rate)
                    
                    if measured_latency > 0:
                        # We measured the buffer/queue latency
                        # For Bluetooth devices, add transmission latency estimate
                        is_bluetooth = self._is_bluetooth_device(device_name)
                        
                        if is_bluetooth:
                            # Measured latency is buffer latency, add Bluetooth transmission latency
                            # Bluetooth transmission typically adds 50-100ms
                            transmission_latency = 0.075  # 75ms average
                            latency = measured_latency + transmission_latency
                            print(f"Measured buffer latency: {measured_latency*1000:.1f}ms, added Bluetooth transmission: {transmission_latency*1000:.1f}ms")
                        else:
                            # Wired device - measured latency should be accurate
                            latency = measured_latency
                            print(f"Measured latency: {latency*1000:.1f}ms")
                    else:
                        # Measurement failed, fall back to estimates
                        print(f"Latency measurement failed for '{device_name}', using estimates...")
                        measure = False  # Fall through to estimate
                
                # Use estimates if measurement failed or not requested
                if not measure or latency == 0.0:
                    is_bluetooth = self._is_bluetooth_device(device_name)
                    
                    if is_bluetooth:
                        # Bluetooth devices typically have 100-200ms total latency
                        latency = 0.150  # 150ms conservative estimate
                        print(f"Using estimated latency for Bluetooth device '{device_name}': {latency*1000:.0f}ms")
                    else:
                        # Wired devices have minimal latency (usually <10ms)
                        latency = 0.010  # 10ms for safety
                        print(f"Using estimated latency for wired device '{device_name}': {latency*1000:.0f}ms")
                
                base_latency = latency
                # Cache the base latency
                self.device_latencies[device_index] = base_latency
            
            # Apply relative adjustment: adjustment is ADDED to base
            # Positive adjustment = delay device (increase latency)
            # Negative adjustment = advance device (decrease latency)
            total_latency = base_latency + manual_adjustment_seconds
            print(f"Applied manual latency adjustment: {manual_adjustment_seconds*1000:.1f}ms (base: {base_latency*1000:.1f}ms, total: {total_latency*1000:.1f}ms)")
        else:
            # No manual adjustment - use measured/estimated latency
            if device_index in self.device_latencies:
                total_latency = self.device_latencies[device_index]
            else:
                # Need to measure or estimate
                latency = 0.0
                
                # Try to measure actual latency if requested
                if measure and _check_sounddevice():
                    print(f"Measuring latency for '{device_name}'...")
                    measured_latency = self._measure_device_latency(device_index, device_name, sample_rate)
                    
                    if measured_latency > 0:
                        is_bluetooth = self._is_bluetooth_device(device_name)
                        
                        if is_bluetooth:
                            transmission_latency = 0.075  # 75ms average
                            latency = measured_latency + transmission_latency
                            print(f"Measured buffer latency: {measured_latency*1000:.1f}ms, added Bluetooth transmission: {transmission_latency*1000:.1f}ms")
                        else:
                            latency = measured_latency
                            print(f"Measured latency: {latency*1000:.1f}ms")
                    else:
                        print(f"Latency measurement failed for '{device_name}', using estimates...")
                        measure = False
                
                # Use estimates if measurement failed or not requested
                if not measure or latency == 0.0:
                    is_bluetooth = self._is_bluetooth_device(device_name)
                    
                    if is_bluetooth:
                        latency = 0.150  # 150ms conservative estimate
                        print(f"Using estimated latency for Bluetooth device '{device_name}': {latency*1000:.0f}ms")
                    else:
                        latency = 0.010  # 10ms for safety
                        print(f"Using estimated latency for wired device '{device_name}': {latency*1000:.0f}ms")
                
                total_latency = latency
                # Cache the latency
                self.device_latencies[device_index] = total_latency
        
        # Ensure non-negative
        return max(0.0, total_latency)
    
    def load_audio_file(self, file_path: str):
        """
        Load an audio file with validation.
        
        Args:
            file_path: Path to the audio file
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported or file is invalid
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        # Validate file extension
        valid_extensions = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma', '.mp4', '.m4v'}
        file_ext = os.path.splitext(file_path.lower())[1]
        if file_ext not in valid_extensions:
            raise ValueError(f"Unsupported audio format: {file_ext}. Supported formats: {', '.join(valid_extensions)}")
        
        # Check file size (basic validation)
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise ValueError(f"Audio file is empty: {file_path}")
        if file_size > 1024 * 1024 * 1024:  # 1GB limit
            raise ValueError(f"Audio file is too large (>1GB): {file_path}")
        
        self.audio_file = file_path
        print(f"Audio file loaded: {os.path.basename(file_path)} ({file_size / (1024*1024):.2f} MB)")
    
    def _load_audio_data(self):
        """Load audio file and convert to numpy array for playback."""
        sample_rate = 44100
        samples = None
        
        # Try to load as WAV first (no ffmpeg needed)
        try:
            import wave
            if self.audio_file.lower().endswith('.wav'):
                with wave.open(self.audio_file, 'rb') as wav_file:
                    sample_rate = wav_file.getframerate()
                    channels = wav_file.getnchannels()
                    frames = wav_file.getnframes()
                    audio_data = wav_file.readframes(frames)
                    
                    if wav_file.getsampwidth() == 2:  # 16-bit
                        samples = np.frombuffer(audio_data, dtype=np.int16)
                    elif wav_file.getsampwidth() == 4:  # 32-bit
                        samples = np.frombuffer(audio_data, dtype=np.int32)
                    else:
                        samples = np.frombuffer(audio_data, dtype=np.int16)
                    
                    # Convert to float32 and normalize
                    samples = samples.astype(np.float32)
                    if samples.dtype == np.int16:
                        samples = samples / 32768.0
                    elif samples.dtype == np.int32:
                        samples = samples / 2147483648.0
                    
                    # Reshape for stereo
                    if channels == 2:
                        samples = samples.reshape((-1, 2))
                    else:
                        samples = np.column_stack((samples, samples))
                    
                    return samples, sample_rate
        except Exception:
            pass  # Fall through to pydub
        
        # Try pydub (requires ffmpeg for MP3)
        global AudioSegment
        if AudioSegment is None:
            try:
                from pydub import AudioSegment
            except ImportError:
                pass
        
        if AudioSegment is not None:
            try:
                audio = AudioSegment.from_file(self.audio_file)
                sample_rate = audio.frame_rate
                
                # Convert to numpy array
                samples = np.array(audio.get_array_of_samples())
                
                # Handle mono/stereo
                if audio.channels == 2:
                    samples = samples.reshape((-1, 2))
                else:
                    samples = np.column_stack((samples, samples))
                
                # Normalize to float32
                if audio.sample_width == 1:
                    samples = samples.astype(np.float32) / 128.0 - 1.0
                elif audio.sample_width == 2:
                    samples = samples.astype(np.float32) / 32768.0
                elif audio.sample_width == 4:
                    samples = samples.astype(np.float32) / 2147483648.0
                else:
                    samples = samples.astype(np.float32) / 32768.0
                
                return samples, sample_rate
            except Exception as e:
                print(f"pydub failed to load audio: {e}")
                if "ffmpeg" in str(e).lower() or "ffprobe" in str(e).lower():
                    print("ffmpeg is required for MP3 files. Install from: https://ffmpeg.org/download.html")
        
        return None, None
    
    def _play_to_device_sync(self, samples, sample_rate, device_index: Optional[int], device_name: str = "Device", start_time=None, ready_event=None, start_event=None, device_num=0):
        """Play audio samples to a specific device with precise synchronization and real-time volume control."""
        if not _check_sounddevice():
            return
        
        stream = None
        try:
            # Get volume for this device (will be updated in real-time, thread-safe)
            volume = self.get_volume(1 if device_num == 0 else 2)
            
            # Create callback function for real-time volume control
            position = [0]  # Use list to allow modification in nested function
            
            # Buffer underrun protection
            buffer_underrun_count = [0]  # Track underruns
            last_callback_time = [None]  # Track callback timing (None for first callback)
            callback_count = [0]  # Track number of callbacks
            
            def callback(outdata, frames, time_info, status):
                if status:
                    # Log status but don't fail on warnings
                    if 'input' in str(status).lower() or 'output' in str(status).lower():
                        logger.warning(f"Audio status (Device {device_num}): {status}")
                
                callback_count[0] += 1
                
                # Monitor callback timing for underrun detection
                # Skip first callback - it can have longer delay due to stream startup
                current_time = time.time()
                if last_callback_time[0] is not None:
                    time_since_last = current_time - last_callback_time[0]
                    expected_interval = frames / sample_rate
                    
                    # Detect potential underruns (callbacks too far apart)
                    # Only check after first few callbacks (startup can be slow)
                    if callback_count[0] > 3 and time_since_last > expected_interval * 2 and time_since_last > 0.1:
                        buffer_underrun_count[0] += 1
                        if buffer_underrun_count[0] <= 3:  # Only warn first few times
                            logger.warning(f"Potential buffer underrun detected on device {device_num} (interval: {time_since_last*1000:.1f}ms, expected: {expected_interval*1000:.1f}ms)")
                
                last_callback_time[0] = current_time
                
                # Get current volume for this device (thread-safe)
                current_volume = self.get_volume(1 if device_num == 0 else 2)
                
                # Calculate how many samples to read
                remaining = len(samples) - position[0]
                if remaining == 0:
                    raise sd.CallbackStop()
                
                # Read samples
                chunk_size = min(frames, remaining)
                chunk = samples[position[0]:position[0] + chunk_size]
                
                # Apply volume in real-time
                if current_volume != 1.0:
                    chunk = chunk * current_volume
                
                # Pad with zeros if needed (end of track or underrun recovery)
                if chunk_size < frames:
                    padding = np.zeros((frames - chunk_size, chunk.shape[1] if len(chunk.shape) > 1 else 1), dtype=chunk.dtype)
                    chunk = np.concatenate([chunk, padding])
                
                # Ensure output buffer is filled (prevent clicks/pops)
                outdata[:] = chunk
                position[0] += chunk_size
                
                # Update position tracking
                self.current_position[device_num] = position[0]
            
            # Signal that this thread is ready
            if ready_event:
                ready_event.set()
            
            # Wait for the start signal
            if start_event:
                start_event.wait()
            
            # Wait until the precise start time with optimized busy-wait
            if start_time is not None:
                wait_time = start_time - time.time()
                if wait_time > 0:
                    # Sleep for most of the wait time, then busy-wait for precision
                    if wait_time > 0.001:  # Only busy-wait for <1ms
                        time.sleep(wait_time - 0.001)
                    # Fine-grained busy-wait only for the last millisecond
                    while time.time() < start_time:
                        pass
            
            # Verify device index is valid
            if device_index is not None:
                try:
                    device_info = sd.query_devices(device_index)
                    print(f"Playing to {device_name} (device {device_index}: '{device_info['name']}') at {time.time():.6f}...")
                except Exception as e:
                    print(f"Warning: Could not query device {device_index}: {e}")
                    print(f"Playing to {device_name} (device {device_index}) at {time.time():.6f}...")
            else:
                print(f"Playing to {device_name} (default device) at {time.time():.6f}...")
            
            # Use OutputStream with callback for real-time volume control
            try:
                stream = sd.OutputStream(
                    samplerate=sample_rate,
                    channels=samples.shape[1] if len(samples.shape) > 1 else 1,
                    device=device_index,
                    callback=callback,
                    dtype=samples.dtype
                )
                # Register stream in consolidated registry (thread-safe)
                self._register_stream(device_num, stream)
                stream.start()
            except Exception as e:
                logger.warning(f"Error creating stream for {device_name}: {e}. Attempting fallback method.")
                # Fallback to sd.play() if streaming fails
                try:
                    # Apply volume before playing
                    samples_with_volume = samples.copy()
                    if volume != 1.0:
                        samples_with_volume = samples_with_volume * volume
                    sd.play(samples_with_volume, samplerate=sample_rate, device=device_index, blocking=False)
                    logger.info(f"Using fallback playback method for {device_name}")
                    stream = None
                except Exception as fallback_error:
                    logger.error(f"Fallback playback also failed for {device_name}: {fallback_error}")
                    # Re-raise to trigger graceful degradation in play() method
                    raise RuntimeError(f"Failed to play to device '{device_name}': {fallback_error}")
            
            # Calculate duration and wait for playback to complete
            total_duration = len(samples) / sample_rate
            
            # Wait for playback to finish, checking for pause/stop
            start_play_time = time.time()
            paused_time = 0.0  # Track total paused time
            pause_start_time = None
            
            try:
                while self.is_playing:
                    try:
                        # Check for pause
                        if self.is_paused:
                            if pause_start_time is None:
                                # Just paused
                                pause_start_time = time.time()
                                try:
                                    # Stop the stream when pausing
                                    if stream is not None:
                                        # Using OutputStream - stop the specific stream
                                        stream.stop()
                                    else:
                                        # Using sd.play() fallback - stop global stream
                                        sd.stop()
                                except Exception as e:
                                    print(f"Error stopping on pause: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    # Continue anyway - pause state is set
                            # Wait while paused - keep the loop running
                            try:
                                time.sleep(0.01)
                            except Exception as e:
                                print(f"Error in pause wait loop: {e}")
                            continue
                    except Exception as e:
                        print(f"Error in pause check: {e}")
                        import traceback
                        traceback.print_exc()
                        # Continue loop - don't exit
                        try:
                            time.sleep(0.01)
                        except:
                            pass
                        continue
                    else:
                        # Not paused (or just resumed)
                        try:
                            if pause_start_time is not None:
                                # Just resumed - add to paused time
                                paused_time += time.time() - pause_start_time
                                pause_start_time = None
                                # Resume playback from where we left off
                                elapsed = (time.time() - start_play_time) - paused_time
                                if elapsed < total_duration and elapsed >= 0:
                                    resume_pos = int(elapsed * sample_rate)
                                    if resume_pos < len(samples):
                                        try:
                                            print(f"Resuming playback from position {resume_pos}/{len(samples)} samples ({elapsed:.2f}s)")
                                            # Update position for callback
                                            position[0] = resume_pos
                                            # Restart stream if using OutputStream
                                            if stream is not None:
                                                stream.start()
                                            else:
                                                # Fallback to sd.play()
                                                current_volume = self.get_volume(1 if device_num == 0 else 2)
                                                samples_with_volume = samples[resume_pos:].copy()
                                                if current_volume != 1.0:
                                                    samples_with_volume = samples_with_volume * current_volume
                                                sd.play(samples_with_volume, samplerate=sample_rate, device=device_index, blocking=False)
                                        except Exception as e:
                                            print(f"Error resuming playback: {e}")
                                            import traceback
                                            traceback.print_exc()
                                            # Don't break - keep trying or wait
                                            try:
                                                time.sleep(0.1)
                                            except:
                                                pass
                                    else:
                                        # Already past the end
                                        print("Cannot resume: already past end of track")
                                        break
                                else:
                                    # Already past the end
                                    print("Cannot resume: already past end of track")
                                    break
                        except Exception as e:
                            print(f"Error in resume logic: {e}")
                            import traceback
                            traceback.print_exc()
                            # Continue loop - don't exit
                            try:
                                time.sleep(0.01)
                            except:
                                pass
                            continue
                    
                    # Only check duration and stream status if not paused
                    if not self.is_paused:
                        try:
                            # Check if we've exceeded the expected duration (accounting for paused time)
                            elapsed = (time.time() - start_play_time) - paused_time
                            if elapsed >= total_duration:
                                break
                            
                            # Check if playback is still active (with timeout)
                            # Note: When paused, stream will be inactive, so we skip this check
                            try:
                                # Check the specific OutputStream if it exists
                                if stream is not None:
                                    # Using OutputStream - check its status directly
                                    if not stream.active:
                                        # Stream ended - check if we should continue
                                        elapsed = (time.time() - start_play_time) - paused_time
                                        if elapsed >= total_duration:
                                            break
                                        # If stream is inactive but we haven't reached the end,
                                        # the stream might have ended prematurely
                                        # In this case, we should wait a bit and check again
                                        time.sleep(0.1)
                                else:
                                    # Using sd.play() fallback - check global stream
                                    global_stream = sd.get_stream()
                                    if global_stream is not None and not global_stream.active:
                                        # Stream ended - check if we should continue
                                        elapsed = (time.time() - start_play_time) - paused_time
                                        if elapsed >= total_duration:
                                            break
                                        # If stream is inactive but we haven't reached the end,
                                        # the stream might have ended prematurely
                                        # In this case, we should wait a bit and check again
                                        time.sleep(0.1)
                            except Exception as e:
                                # Stream might not be accessible, check by time only
                                # Only print error if it's not the expected "play()/rec()/playrec() was not called yet" error
                                error_msg = str(e)
                                if "play()/rec()/playrec() was not called yet" not in error_msg:
                                    print(f"Error checking stream status: {e}")
                                elapsed = (time.time() - start_play_time) - paused_time
                                if elapsed >= total_duration:
                                    break
                        except Exception as e:
                            print(f"Error in duration check: {e}")
                            import traceback
                            traceback.print_exc()
                            # Continue loop - don't exit
                    
                    try:
                        time.sleep(0.01)
                    except Exception as e:
                        print(f"Error in sleep: {e}")
                        # Continue anyway
            except Exception as e:
                print(f"Error in playback loop: {e}")
                import traceback
                traceback.print_exc()
            finally:
                # Stop playback - always try to stop, even if there was an error
                # But only if not paused (when paused, we want to keep the stream stopped but thread alive)
                try:
                    if not self.is_paused:
                        if stream is not None:
                            # Using OutputStream - stop and close the specific stream
                            try:
                                stream.stop()
                                stream.close()
                            except Exception as e:
                                print(f"Error stopping/closing stream: {e}")
                            finally:
                                # Unregister stream from registry
                                self._unregister_stream(device_num)
                        else:
                            # Using sd.play() fallback - stop global stream
                            sd.stop()
                except Exception as e:
                    print(f"Error stopping playback: {e}")
                    # Don't re-raise - this is cleanup
                finally:
                    # Always unregister stream if it exists
                    if stream is not None:
                        self._unregister_stream(device_num)
            
        except Exception as e:
            print(f"Error playing to {device_name}: {e}")
            import traceback
            traceback.print_exc()
            try:
                if stream is not None:
                    # Using OutputStream - stop and close the specific stream
                    try:
                        stream.stop()
                        stream.close()
                    except:
                        pass
                    finally:
                        # Unregister stream from registry
                        self._unregister_stream(device_num)
                else:
                    # Using sd.play() fallback - stop global stream
                    sd.stop()
            except:
                pass
            finally:
                # Always unregister stream if it exists
                if stream is not None:
                    self._unregister_stream(device_num)
    
    def _play_with_pygame(self):
        """Play audio using pygame (fallback method)."""
        try:
            pygame.mixer.music.load(self.audio_file)
            pygame.mixer.music.set_volume(self.get_volume(1))  # Use device1 volume for pygame
            pygame.mixer.music.play()
            
            # Wait for playback to finish
            while pygame.mixer.music.get_busy() and self.is_playing:
                if self.is_paused:
                    pygame.mixer.music.pause()
                    self.pause_event.wait()  # Wait until unpaused
                    pygame.mixer.music.unpause()
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Error during pygame playback: {e}")
        finally:
            pygame.mixer.music.stop()
    
    def play(self):
        """Play audio to selected device(s) simultaneously."""
        if self.audio_file is None:
            print("No audio loaded. Please load an audio file first.")
            return
        
        if self.is_playing:
            print("Already playing audio.")
            return
        
        self.is_playing = True
        self.play_threads = []
        
        try:
            if _check_sounddevice() and (self.device1 is not None or self.device2 is not None):
                # Load audio data once (shared by all devices)
                print("Loading audio file...")
                samples, sample_rate = self._load_audio_data()
                
                if samples is None or sample_rate is None:
                    print("Failed to load audio data. Falling back to pygame.")
                    self._play_with_pygame()
                    return
                
                # Play to selected devices using sounddevice
                devices = []
                if self.device1 is not None:
                    # Verify device 1 exists
                    try:
                        device_info = sd.query_devices(self.device1)
                        devices.append((self.device1, f"Device 1 ({device_info['name']})"))
                        logger.info(f"Device 1 configured: '{device_info['name']}' (index: {self.device1})")
                    except Exception as e:
                        logger.warning(f"Device 1 (index {self.device1}) not found or unavailable: {e}. Continuing with remaining devices.")
                        # Graceful degradation: continue with other devices
                if self.device2 is not None:
                    # Verify device 2 exists
                    try:
                        device_info = sd.query_devices(self.device2)
                        devices.append((self.device2, f"Device 2 ({device_info['name']})"))
                        logger.info(f"Device 2 configured: '{device_info['name']}' (index: {self.device2})")
                    except Exception as e:
                        logger.warning(f"Device 2 (index {self.device2}) not found or unavailable: {e}. Continuing with remaining devices.")
                        # Graceful degradation: continue with other devices
                
                if devices:
                    logger.info(f"Playing to {len(devices)} device(s) simultaneously...")
                    # If we had 2 devices but only 1 is available, inform user
                    if (self.device1 is not None or self.device2 is not None) and len(devices) == 1:
                        logger.warning("One device is unavailable. Continuing playback on the remaining device.")
                    
                    # Create synchronization events
                    import threading
                    ready_events = [threading.Event() for _ in devices]
                    start_event = threading.Event()
                    
                    # Measure latency for each device before playing
                    logger.info("Measuring device latencies...")
                    device_latencies = []
                    for device_idx, device_name in devices:
                        latency = self._get_device_latency(device_idx, device_name, sample_rate, measure=True)
                        device_latencies.append(latency)
                    logger.info("Latency measurement complete.")
                    
                    # Find the maximum latency (device that needs to start earliest)
                    max_latency = max(device_latencies) if device_latencies else 0.0
                    
                    # Calculate target time when audio should be heard
                    # Need enough time for thread setup (50ms) + max latency to ensure earliest device can start
                    target_audio_time = time.time() + 0.05 + max_latency
                    
                    logger.info(f"Latency compensation: max={max_latency*1000:.0f}ms, target audio time={target_audio_time:.6f}")
                    
                    # Start all playback threads with device-specific start times
                    # Track which devices successfully start
                    successful_devices = []
                    for i, (device_idx, device_name) in enumerate(devices):
                        # Calculate device-specific start time
                        # Devices with higher latency start EARLIER so audio arrives at the same time
                        # Each device starts at: target_audio_time - device_latency
                        device_latency = device_latencies[i]
                        device_start_time = target_audio_time - device_latency
                        
                        logger.info(f"Device {i+1} '{device_name}': latency={device_latency*1000:.0f}ms, start_time={device_start_time:.6f} (will be heard at {target_audio_time:.6f})")
                        
                        try:
                            # Pass original samples - volume will be applied in real-time
                            thread = threading.Thread(
                                target=self._play_to_device_sync,
                                args=(samples, sample_rate, device_idx, device_name, device_start_time, ready_events[i], start_event, i),  # Pass device-specific start time
                                daemon=True
                            )
                            thread.start()
                            self.play_threads.append(thread)
                            successful_devices.append(device_name)
                        except Exception as e:
                            logger.error(f"Failed to start playback thread for device '{device_name}': {e}. Continuing with remaining devices.")
                            # Graceful degradation: continue with other devices
                            # Mark this device's ready event as set so we don't wait for it
                            if i < len(ready_events):
                                ready_events[i].set()
                    
                    # Warn if some devices failed to start
                    if len(successful_devices) < len(devices):
                        failed_count = len(devices) - len(successful_devices)
                        logger.warning(f"{failed_count} device(s) failed to start. Playback continuing on {len(successful_devices)} device(s).")
                    
                    # If no devices started successfully, this is a critical error
                    if not successful_devices:
                        logger.error("All devices failed to start. Cannot play audio.")
                        raise RuntimeError("All audio devices failed to start. Please check your audio device connections and try again.")
                    
                    # Wait for all threads to be ready
                    logger.info("Waiting for all devices to be ready...")
                    for event in ready_events:
                        event.wait(timeout=1.0)
                    
                    # Small delay to ensure all threads are waiting
                    time.sleep(0.01)
                    
                    # Signal all threads to start (they will start at their individual start times)
                    logger.info(f"Signaling all devices to start (with latency compensation)...")
                    start_event.set()
                    
                    # Wait for all threads to finish
                    # But if paused, we should wait until resumed or stopped
                    # Keep waiting if playing OR paused (so we can resume)
                    try:
                        while self.is_playing or self.is_paused:
                            all_finished = True
                            for thread in self.play_threads:
                                try:
                                    if thread.is_alive():
                                        all_finished = False
                                        thread.join(timeout=0.1)
                                except Exception as e:
                                    print(f"Error joining thread: {e}")
                                    import traceback
                                    traceback.print_exc()
                                    # Continue checking other threads
                            
                            # If paused, keep waiting (don't exit play() method)
                            # Threads are still alive (waiting in pause loop)
                            if self.is_paused:
                                try:
                                    time.sleep(0.1)
                                except Exception as e:
                                    print(f"Error in pause wait: {e}")
                                continue
                            
                            # If not playing anymore (and not paused), we're done
                            if not self.is_playing:
                                print("Playback stopped")
                                break
                            
                            # If all threads finished and we're not paused, we're done
                            if all_finished and not self.is_paused:
                                print("All devices finished playing")
                                break
                            
                            # If threads are still alive, keep waiting
                            if not all_finished:
                                try:
                                    time.sleep(0.1)
                                except Exception as e:
                                    print(f"Error waiting for threads: {e}")
                                continue
                            
                            # Should not reach here, but if we do, keep waiting
                            try:
                                time.sleep(0.1)
                            except Exception as e:
                                print(f"Error in wait loop: {e}")
                    except Exception as e:
                        print(f"Error in thread join loop: {e}")
                        import traceback
                        traceback.print_exc()
                        # If paused, keep waiting - don't exit play() method
                        if self.is_paused:
                            try:
                                while self.is_paused and (self.is_playing or True):  # Keep waiting while paused
                                    try:
                                        time.sleep(0.1)
                                    except Exception as sleep_error:
                                        print(f"Error in pause wait: {sleep_error}")
                                        # Continue waiting
                            except Exception as wait_error:
                                print(f"Error in pause wait loop: {wait_error}")
                                import traceback
                                traceback.print_exc()
                                # Don't re-raise - keep the app running
                                # Continue waiting if still paused
                                if self.is_paused:
                                    try:
                                        time.sleep(0.1)
                                    except:
                                        pass
                else:
                    # No devices available - this is a problem
                    logger.error("No valid audio devices available. Cannot play audio.")
                    raise RuntimeError("No valid audio devices available. Please check your audio device connections and try again.")
            else:
                # Fallback to pygame
                self._play_with_pygame()
                
        except Exception as e:
            print(f"Error during playback: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Only set is_playing = False if we're not paused
            # If paused, we want to keep is_playing = True so resume works
            # The stop() method will set is_playing = False when actually stopping
            if not self.is_paused:
                self.is_playing = False
                print("Playback completed.")
            else:
                # We're paused - don't set is_playing = False, and don't print "completed"
                print("Playback paused - play() method waiting for resume or stop")
            
            # Ensure all streams are stopped (but only if not paused)
            if not self.is_paused:
                if _check_sounddevice():
                    try:
                        # Close any remaining streams using consolidated registry
                        self._close_all_streams()
                        # Stop any active playback
                        sd.stop()
                    except:
                        pass
    
    def pause(self):
        """Pause audio playback."""
        try:
            if not self.is_playing:
                print("Cannot pause: playback is not active")
                return
            
            if self.is_paused:
                print("Already paused")
                return
            
            # Set pause state - wrap in try/except to prevent crashes
            try:
                self.is_paused = True
                print("Playback paused")
            except Exception as e:
                print(f"Error setting pause state: {e}")
                import traceback
                traceback.print_exc()
                # Don't re-raise - try to continue
                return
            
            if hasattr(self, 'pause_event'):
                try:
                    self.pause_event.clear()
                except Exception as e:
                    print(f"Error clearing pause event: {e}")
                    # Continue anyway
        except Exception as e:
            print(f"Critical error in pause(): {e}")
            import traceback
            traceback.print_exc()
            # Don't re-raise - prevent crash
            
            # Pause pygame if using it
            if not _check_sounddevice() or (self.device1 is None and self.device2 is None):
                try:
                    pygame.mixer.music.pause()
                except Exception as e:
                    print(f"Error pausing pygame: {e}")
            
            # For sounddevice, the playback loop will handle pausing by checking is_paused
            # We don't need to call sd.stop() here - the playback loop will do it
            # This ensures the playback loop stays alive and can resume correctly
            
            print("Playback paused")
        except Exception as e:
            print(f"Error in pause(): {e}")
            import traceback
            traceback.print_exc()
    
    def resume(self):
        """Resume audio playback."""
        try:
            if not self.is_playing:
                print("Cannot resume: playback is not active")
                return
            
            if not self.is_paused:
                print("Playback is not paused")
                return
            
            self.is_paused = False
            if hasattr(self, 'pause_event'):
                self.pause_event.set()
            
            # Resume pygame if using it
            if not _check_sounddevice() or (self.device1 is None and self.device2 is None):
                try:
                    pygame.mixer.music.unpause()
                except Exception as e:
                    print(f"Error resuming pygame: {e}")
            
            print("Playback resumed")
        except Exception as e:
            print(f"Error in resume(): {e}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Stop audio playback."""
        try:
            self.is_playing = False
            self.is_paused = False
            self.pause_event.set()  # Unblock any waiting threads
            
            # Stop all sounddevice streams using consolidated registry
            if _check_sounddevice():
                try:
                    # Close all registered streams (thread-safe)
                    self._close_all_streams()
                    
                    # Also stop any global sounddevice streams
                    try:
                        sd.stop()
                    except Exception as e:
                        print(f"Error calling sd.stop(): {e}")
                except Exception as e:
                    print(f"Error in stop() sounddevice section: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Stop pygame
            try:
                pygame.mixer.music.stop()
            except Exception as e:
                print(f"Error stopping pygame: {e}")
            
            # Wait for threads to finish (with timeout to prevent hanging)
            # Don't wait too long - daemon threads will be cleaned up automatically
            threads_to_join = self.play_threads[:]  # Copy list
            for thread in threads_to_join:
                try:
                    if thread and thread.is_alive():
                        thread.join(timeout=0.1)  # Very short timeout - don't block
                except Exception as e:
                    print(f"Error joining thread: {e}")
                    # Continue - don't let thread join errors stop the stop process
                except AttributeError:
                    # Thread might be None or invalid
                    pass
            
            # Clear thread list
            self.play_threads.clear()
            
        except Exception as e:
            print(f"Critical error in stop(): {e}")
            import traceback
            traceback.print_exc()
            # Even if there's an error, try to reset state
            try:
                self.is_playing = False
                self.is_paused = False
                self.pause_event.set()
            except:
                pass
            # Don't re-raise - we want to continue even if stop() had errors
    
    def set_devices(self, device1: Optional[int] = None, device2: Optional[int] = None):
        """Update the selected output devices."""
        self.device1 = device1
        self.device2 = device2


def main():
    """Main function to run the audio player."""
    print("=" * 60)
    print("Simple Audio Player")
    print("=" * 60)
    
    # Get audio file path
    print("\nEnter the path to your audio file:")
    audio_file = input("Audio file path: ").strip().strip('"')
    
    if not audio_file:
        print("Error: No audio file specified.")
        return
    
    if not os.path.exists(audio_file):
        print(f"Error: File not found: {audio_file}")
        return
    
    # Create player and load audio
    player = SynchronizedAudioPlayer()
    
    try:
        player.load_audio_file(audio_file)
    except Exception as e:
        print(f"Error loading audio file: {e}")
        return
    
    # Play audio
    print("\nStarting playback...")
    print("Press Ctrl+C to stop.")
    
    try:
        player.play()
    except KeyboardInterrupt:
        print("\nPlayback interrupted by user.")
        player.stop()


if __name__ == "__main__":
    main()
