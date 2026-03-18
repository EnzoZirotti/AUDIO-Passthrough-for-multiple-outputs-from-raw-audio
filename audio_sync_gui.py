"""
Audio Player GUI with SoundCloud Streaming
Supports local files and SoundCloud streaming with flexible search.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional
import threading
import os
import time
import sys
from collections import deque
from audio_sync_player import SynchronizedAudioPlayer
from bluetoothstreamer.utils.validators import validate_audio_file, validate_device_index, sanitize_filename

# Import Round 8 components (optional, for advanced buffering)
try:
    from bluetoothstreamer.core import FrontWalkBuffer, get_hpet_timer
    ROUND8_AVAILABLE = True
except ImportError:
    ROUND8_AVAILABLE = False
    print("Round 8 components not available - using standard buffer")

# Import Round 9 distributed computing components
try:
    from bluetoothstreamer.streaming import MasterNode, FleetNode
    DISTRIBUTED_AVAILABLE = True
except ImportError:
    DISTRIBUTED_AVAILABLE = False
    print("Distributed computing components not available")

# Import Multi-Bluetooth Sync Components (Phase 1-3)
try:
    from bluetoothstreamer.core import (
        DynamicLatencyMonitor,
        SyncMonitor,
        MultiDeviceSyncCoordinator,
        BluetoothJitterMeasurer,
        ClockSynchronizer,
        BluetoothCodecDetector,
        AdaptiveBufferManager,
        BluetoothSignalMonitor,
        DeviceManager
    )
    MULTI_BLUETOOTH_SYNC_AVAILABLE = True
except ImportError as e:
    MULTI_BLUETOOTH_SYNC_AVAILABLE = False
    print(f"Multi-Bluetooth sync components not available: {e}")
    DeviceManager = None

# Set up exception handler to prevent crashes
def handle_exception(exc_type, exc_value, exc_traceback):
    """Handle unhandled exceptions to prevent app crashes."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Don't exit on SystemExit from cleanup threads - only allow SystemExit from main thread
    # This prevents cleanup errors from closing the app
    if issubclass(exc_type, SystemExit):
        # Only allow SystemExit if it's from the main thread
        import threading
        if threading.current_thread() is threading.main_thread():
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
        else:
            # SystemExit from non-main thread - log it but don't exit
            print(f"⚠ SystemExit caught from non-main thread: {exc_value}")
            import traceback
            traceback.print_exc()
        return
    print(f"\nUnhandled exception: {exc_type.__name__}: {exc_value}")
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    print("\nApplication will continue running...")

sys.excepthook = handle_exception

# Try to import streaming services
try:
    from streaming_service import StreamingManager
    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False
    print("SoundCloud streaming not available. Install: pip install soundcloud-lib requests")


class AudioSyncGUI:
    """GUI application with SoundCloud streaming support."""
    
    @staticmethod
    def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius=10, **kwargs):
        """Create a rounded rectangle on a canvas."""
        points = []
        # Top-left corner
        points.extend([x1 + radius, y1])
        points.extend([x1 + radius, y1])
        points.extend([x1, y1])
        points.extend([x1, y1 + radius])
        # Top-right corner
        points.extend([x2 - radius, y1])
        points.extend([x2, y1])
        points.extend([x2, y1 + radius])
        # Bottom-right corner
        points.extend([x2, y2 - radius])
        points.extend([x2, y2])
        points.extend([x2 - radius, y2])
        # Bottom-left corner
        points.extend([x1 + radius, y2])
        points.extend([x1, y2])
        points.extend([x1, y2 - radius])
        
        return canvas.create_polygon(points, smooth=True, splinesteps=16, **kwargs)
    
    def __init__(self, root):
        self.root = root
        self.root.title("Bluetooth Streamer - Multi-Device Audio Player")
        self.root.geometry("800x850")
        # Make window resizable
        self.root.resizable(True, True)
        # Set minimum window size (smaller to allow more flexibility)
        self.root.minsize(400, 300)
        
        # Prevent window from closing unexpectedly - handle close event properly
        def on_closing():
            """Handle window close event."""
            if self.passthrough_active:
                # If passthrough is active, stop it first
                self.stop_audio_passthrough()
                # Don't close immediately - wait a moment for cleanup
                self.root.after(500, self.root.destroy)
            else:
                # Safe to close
                self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Soft pastel color scheme with darker purple and blue backlighting
        self.colors = {
            'bg_primary': '#9098C8',      # Even darker lavender-blue
            'bg_secondary': '#8088B8',    # Even darker purple-blue
            'bg_dark': '#6870A8',         # Even darker purple-blue
            'accent_primary': '#5A6AA8',  # Even darker pastel blue
            'accent_success': '#6A7AA8',  # Even darker pastel blue-green
            'accent_danger': '#A88098',   # Even darker pastel purple-pink
            'accent_warning': '#9880A8',  # Even darker pastel purple
            'text_primary': '#0D0D2A',    # Even darker purple-gray
            'text_secondary': '#2A2A4A', # Even darker purple-gray
            'text_light': '#C0C0D0',     # Even darker purple-white
            'border': '#7A8098',          # Even darker purple-blue border
            'hover_primary': '#4A5A98',   # Even darker pastel blue
            'hover_success': '#5A6A98',   # Even darker pastel blue-green
            'hover_danger': '#987088'     # Even darker pastel purple-pink
        }
        
        # Configure root window
        self.root.configure(bg=self.colors['bg_primary'])
        
        # Prevent window from closing unexpectedly - handle close event properly
        def on_closing():
            """Handle window close event."""
            if hasattr(self, 'passthrough_active') and self.passthrough_active:
                # If passthrough is active, stop it first
                self.stop_audio_passthrough()
                # Don't close immediately - wait a moment for cleanup
                self.root.after(1000, self.root.destroy)
            else:
                # Safe to close
                self.root.destroy()
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        
        # Modern font settings
        self.fonts = {
            'title': ('Segoe UI', 14, 'bold'),
            'heading': ('Segoe UI', 11, 'bold'),
            'body': ('Segoe UI', 10),
            'small': ('Segoe UI', 9),
            'button': ('Segoe UI', 10, 'bold')
        }
        
        self.player = None
        self.audio_file_path = None
        self.streaming_manager = None
        self.device1_index = None
        self.device2_index = None
        self.audio_devices = []
        self.device1_latency_adjustment = 0.0  # Latency adjustment in milliseconds
        self.device2_latency_adjustment = 0.0  # Latency adjustment in milliseconds
        self.device1_measured_latency = 0.0  # Measured latency in milliseconds
        self.device2_measured_latency = 0.0  # Measured latency in milliseconds
        
        # Thread-safe volume cache (to avoid blocking audio callbacks during window movement)
        self._volume_cache_lock = threading.Lock()
        self._volume_cache = {1: 1.0, 2: 1.0}  # device_num -> volume (0.0 to 1.0)
        
        # Round 8: Front Walk Buffer configuration (default: False for backward compatibility)
        # Set to True to use HPET timestamps and system clock-based playback
        self.use_front_walk_buffer = False  # Can be enabled via environment variable or GUI option
        if os.environ.get('BLUETOOTHSTREAMER_USE_FRONT_WALK_BUFFER', '').lower() in ('true', '1', 'yes'):
            if ROUND8_AVAILABLE:
                self.use_front_walk_buffer = True
                print("Round 8: Front Walk Buffer enabled via environment variable")
            else:
                print("Warning: Front Walk Buffer requested but Round 8 components not available")
        
        # Round 9: Distributed computing configuration
        self.distributed_mode = tk.StringVar(value="local")  # "local", "master", "fleet"
        self.master_node: Optional[MasterNode] = None
        self.fleet_node: Optional[FleetNode] = None
        self.master_host = tk.StringVar(value="127.0.0.1")
        self.master_udp_port = tk.IntVar(value=5000)
        self.master_tcp_port = tk.IntVar(value=5001)
        self.fleet_status_update_thread: Optional[threading.Thread] = None
        self.reference_device = None  # Device with highest latency (for sync coordinator)
        
        # Multi-Bluetooth Sync Components (Phase 1-3)
        if MULTI_BLUETOOTH_SYNC_AVAILABLE:
            try:
                # Initialize sync coordinator (manages all other components)
                def latency_measurement_callback(device_index, device_name):
                    """Callback to measure device latency."""
                    if hasattr(self, 'player') and self.player is not None:
                        try:
                            import sounddevice as sd
                            device_info = sd.query_devices(device_index)
                            sample_rate = int(device_info.get('default_samplerate', 44100))
                            latency = self.player._get_device_latency(device_index, device_name, sample_rate, measure=True)
                            return latency
                        except:
                            return None
                    return None
                
                def position_callback(device_index):
                    """Callback to get device position."""
                    device_num = None
                    for num, idx in [(1, self.device1_index), (2, self.device2_index)]:
                        if idx == device_index:
                            device_num = num
                            break
                    
                    if device_num and hasattr(self, 'device_read_indices') and hasattr(self, 'audio_buffer'):
                        with getattr(self, 'buffer_lock', threading.Lock()):
                            read_index = self.device_read_indices.get(device_num, 0)
                            buffer_size = len(self.audio_buffer) if hasattr(self, 'audio_buffer') else 0
                            return read_index, buffer_size
                    return 0, 0
                
                def correction_callback(device_index, correction_samples):
                    """
                    Callback to apply sync correction.
                    
                    DISABLED: Real-time corrections during playback cause stuttering.
                    We rely on initial synchronization before playback starts instead.
                    All sync adjustments happen BEFORE audio starts playing.
                    """
                    # No-op: Do not apply corrections during playback
                    # Initial sync is handled by time-based delay before streams start
                    pass
                
                self.sync_coordinator = MultiDeviceSyncCoordinator(
                    latency_measurement_callback=latency_measurement_callback,
                    position_callback=position_callback,
                    correction_callback=correction_callback
                )
                
                # Initialize sub-components
                self.jitter_measurer = BluetoothJitterMeasurer()
                self.clock_synchronizer = ClockSynchronizer()
                self.codec_detector = BluetoothCodecDetector()
                self.buffer_manager = AdaptiveBufferManager()
                self.signal_monitor = BluetoothSignalMonitor()
                
                # Set up signal monitor callbacks
                self.signal_monitor.set_latency_callback(lambda idx: self.sync_coordinator.latency_monitor.get_latency(idx) * 1000.0)
                
                print("✓ Multi-Bluetooth sync components initialized")
            except Exception as e:
                print(f"Warning: Could not initialize multi-Bluetooth sync components: {e}")
                import traceback
                traceback.print_exc()
                self.sync_coordinator = None
                self.jitter_measurer = None
                self.clock_synchronizer = None
                self.codec_detector = None
                self.buffer_manager = None
                self.signal_monitor = None
        else:
            self.sync_coordinator = None
            self.jitter_measurer = None
            self.clock_synchronizer = None
            self.codec_detector = None
            self.buffer_manager = None
            self.signal_monitor = None
        
        # Playlist management
        self.playlist = []  # List of {'type': 'local'|'streaming', 'path': str, 'title': str, 'artist': str}
        self.current_playlist_index = -1
        self.playlist_playing = False
        self.playlist_advancing = False  # Flag to prevent race conditions when advancing
        
        if STREAMING_AVAILABLE:
            try:
                self.streaming_manager = StreamingManager()
            except Exception as e:
                print(f"Warning: Could not initialize streaming: {e}")
        
        # Load available audio devices
        self.refresh_audio_devices()
        
        self.setup_ui()
        
        # Update device combos after UI is fully set up
        self.root.after(100, self.update_device_combos)
        self.root.after(100, self.update_device_combos_sc)
    
    def refresh_audio_devices(self):
        """Refresh the list of available audio devices."""
        try:
            print("Refreshing audio devices...")
            self.audio_devices = SynchronizedAudioPlayer.get_audio_devices()
            print(f"Found {len(self.audio_devices)} audio devices:")
            for d in self.audio_devices:
                print(f"  - {d['name']} (index: {d['index']})")
            
            if not self.audio_devices or len(self.audio_devices) == 0:
                print("WARNING: No devices found!")
                self.audio_devices = [{'index': None, 'name': 'Default Output Device'}]
        except Exception as e:
            print(f"Error refreshing audio devices: {e}")
            import traceback
            traceback.print_exc()
            self.audio_devices = [{'index': None, 'name': 'Default Output Device'}]
        
    def setup_ui(self):
        """Set up the user interface."""
        # Configure ttk styles for soft pastel look
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure notebook style (soft pastel theme)
        style.configure('TNotebook', background=self.colors['bg_primary'], borderwidth=0)
        style.configure('TNotebook.Tab', 
                       padding=[20, 12], 
                       font=self.fonts['body'],
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'],
                       borderwidth=0,
                       relief='flat')
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['accent_primary'])],
                 foreground=[('selected', self.colors['text_light'])],
                 expand=[('selected', [1, 1, 1, 0])])
        
        # Configure LabelFrame style (soft pastel theme with rounded appearance)
        style.configure('TLabelframe', 
                       background=self.colors['bg_secondary'],
                       borderwidth=1,
                       relief='flat',
                       bordercolor=self.colors['border'])
        style.configure('TLabelframe.Label',
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text_light'],
                       font=self.fonts['heading'])
        
        # Configure Frame style
        style.configure('TFrame', background=self.colors['bg_secondary'])
        
        # Configure Combobox style (soft pastel theme)
        style.configure('TCombobox', 
                       fieldbackground=self.colors['bg_primary'],
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       relief='flat')
        style.map('TCombobox',
                 fieldbackground=[('readonly', self.colors['bg_primary'])],
                 selectbackground=[('readonly', self.colors['accent_primary'])],
                 selectforeground=[('readonly', self.colors['text_light'])])
        
        # Configure Button style (soft pastel theme)
        style.configure('TButton', 
                       background=self.colors['accent_primary'], 
                       foreground=self.colors['text_light'], 
                       font=self.fonts['button'], 
                       relief='flat', 
                       borderwidth=0,
                       padding=[15, 8])
        style.map('TButton', 
                 background=[('active', self.colors['hover_primary'])])
        
        # Configure Scrollbar style (soft pastel theme)
        style.configure('TScrollbar', 
                       background=self.colors['bg_secondary'], 
                       troughcolor=self.colors['bg_primary'], 
                       bordercolor=self.colors['border'],
                       arrowcolor=self.colors['text_secondary'],
                       borderwidth=0,
                       relief='flat')
        style.map('TScrollbar', 
                 background=[('active', self.colors['accent_primary'])])
        
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Local File Tab
        local_frame = ttk.Frame(notebook)
        notebook.add(local_frame, text="Local Files")
        self.setup_local_tab(local_frame)
        
        # SoundCloud Tab
        if STREAMING_AVAILABLE:
            stream_frame = ttk.Frame(notebook)
            notebook.add(stream_frame, text="SoundCloud")
            self.setup_streaming_tab(stream_frame)
        
        # Playlist Tab
        playlist_frame = ttk.Frame(notebook)
        notebook.add(playlist_frame, text="Playlist")
        self.setup_playlist_tab(playlist_frame)
        
        # Setup Help Tab - Hidden per user request
        # help_frame = ttk.Frame(notebook)
        # notebook.add(help_frame, text="Multi-Device Setup")
        # self.setup_help_tab(help_frame)
        
        # Modern status bar (soft pastel theme)
        status_frame = tk.Frame(self.root, bg=self.colors['bg_secondary'], height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            text="✓ Ready",
            fg=self.colors['text_primary'],
            bg=self.colors['bg_secondary'],
            anchor=tk.W,
            padx=15,
            font=self.fonts['small']
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.Y)
    
    def setup_local_tab(self, parent):
        """Set up the local file tab with audio pass-through."""
        # Configure parent frame background
        parent.configure(style='TFrame')
        
        # Create scrollable canvas with scrollbar
        canvas = tk.Canvas(parent, bg=self.colors['bg_primary'], highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview, 
                                 bg=self.colors['bg_secondary'], troughcolor=self.colors['bg_dark'],
                                 activebackground=self.colors['accent_primary'])
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg_primary'])
        
        def update_scrollregion(event=None):
            """Update the scroll region to include all content."""
            canvas.update_idletasks()
            scrollable_frame.update_idletasks()
            # Get the actual required size of the scrollable frame
            req_width = scrollable_frame.winfo_reqwidth()
            req_height = scrollable_frame.winfo_reqheight()
            
            # Also check bbox as fallback
            bbox = canvas.bbox("all")
            if bbox:
                # Use the maximum of required height and bbox height, plus padding
                max_height = max(req_height, bbox[3]) + 50  # Extra padding for safety
                max_width = max(req_width, bbox[2]) + 20
                canvas.configure(scrollregion=(0, 0, max_width, max_height))
            elif req_height > 0:
                # Fallback to required size if bbox is not available
                canvas.configure(scrollregion=(0, 0, req_width + 20, req_height + 50))
            else:
                canvas.configure(scrollregion=(0, 0, 0, 0))
        
        def configure_canvas_width(event):
            """Configure canvas window width to match canvas width."""
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            # Update scroll region when canvas is resized
            parent.after(10, update_scrollregion)
        
        # Update scroll region whenever scrollable frame changes
        scrollable_frame.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        canvas.bind("<Configure>", configure_canvas_width)
        # Also update on window resize
        parent.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Update scroll region multiple times to ensure all content is captured
        parent.after(50, update_scrollregion)
        parent.after(100, update_scrollregion)
        parent.after(200, update_scrollregion)
        parent.after(500, update_scrollregion)  # One more delayed update
        
        # Audio pass-through frame
        passthrough_frame = ttk.LabelFrame(scrollable_frame, text="🎵 System Audio Pass-Through", padding=15)
        passthrough_frame.pack(fill=tk.X, padx=15, pady=10)
        
        info_label = tk.Label(
            passthrough_frame,
            text="Capture and route system audio (whatever is playing on your computer) to the selected output devices.\n"
                 "💡 Tip: Virtual Audio Cables provide raw audio capture (bypasses Windows volume mixer).",
            wraplength=700,
            anchor=tk.W,
            fg=self.colors['accent_primary'],
            bg=self.colors['bg_secondary'],
            font=self.fonts['small'],
            justify=tk.LEFT
        )
        info_label.pack(fill=tk.X, pady=(0, 10))
        
        self.passthrough_status_label = tk.Label(
            passthrough_frame,
            text="✓ Ready - Select output devices and click Start Pass-Through",
            wraplength=700,
            anchor=tk.W,
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary'],
            font=self.fonts['small']
        )
        self.passthrough_status_label.pack(fill=tk.X, pady=(0, 10))
        
        # Ready Mode Indicator - Large, prominent visual indicator
        ready_indicator_frame = tk.Frame(passthrough_frame, bg=self.colors['bg_secondary'], relief=tk.FLAT, bd=0, highlightthickness=1, highlightbackground=self.colors['border'], highlightcolor=self.colors['border'])
        ready_indicator_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.ready_mode_indicator = tk.Label(
            ready_indicator_frame,
            text="",
            font=('Segoe UI', 18, 'bold'),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_secondary'],
            height=3,
            wraplength=700,
            justify=tk.CENTER
        )
        self.ready_mode_indicator.pack(fill=tk.X, padx=15, pady=15)
        
        passthrough_btn_frame = tk.Frame(passthrough_frame, bg=self.colors['bg_secondary'])
        passthrough_btn_frame.pack(pady=5)
        
        self.start_passthrough_btn = tk.Button(
            passthrough_btn_frame,
            text="▶ Start Pass-Through",
            command=self.start_audio_passthrough,
            bg=self.colors['accent_success'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=22,
            height=2,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_success'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=15,
            pady=8,
            highlightthickness=0
        )
        self.start_passthrough_btn.pack(side=tk.LEFT, padx=8)
        
        self.stop_passthrough_btn = tk.Button(
            passthrough_btn_frame,
            text="⏹ Stop Pass-Through",
            command=self.stop_audio_passthrough,
            bg=self.colors['accent_danger'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=22,
            height=2,
            state=tk.DISABLED,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_danger'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=15,
            pady=8,
            highlightthickness=0
        )
        self.stop_passthrough_btn.pack(side=tk.LEFT, padx=8)
        
        # Ready Mode is now always enabled (checkbox removed per user request)
        # Ready Mode logic: Start passthrough immediately and wait for audio (eliminates startup delay)
        self.passthrough_ready_mode = tk.BooleanVar(value=True)  # Always enabled
        
        # Round 9: Distributed Computing Mode Selection
        if DISTRIBUTED_AVAILABLE:
            distributed_frame = ttk.LabelFrame(passthrough_frame, text="", padding=10)
            distributed_frame.pack(fill=tk.X, pady=(10, 0))
            
            mode_frame = tk.Frame(distributed_frame, bg=self.colors['bg_secondary'])
            mode_frame.pack(fill=tk.X, pady=5)
            
            # Mode label hidden since buttons are hidden
            mode_label = tk.Label(mode_frame, text="Mode:", width=8, anchor=tk.W,
                    bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                    font=self.fonts['body'])
            mode_label.pack(side=tk.LEFT, padx=5)
            mode_label.pack_forget()  # Hide label since buttons are hidden
            
            # Local radio button hidden per user request
            # tk.Radiobutton(mode_frame, text="Local", variable=self.distributed_mode, value="local",
            #               bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
            #               font=self.fonts['body'], selectcolor=self.colors['bg_secondary'],
            #               command=self.on_distributed_mode_changed).pack(side=tk.LEFT, padx=10)
            
            # Master and Fleet buttons hidden per user request (functionality preserved)
            self.master_radio = tk.Radiobutton(mode_frame, text="Master", variable=self.distributed_mode, value="master",
                          bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                          font=self.fonts['body'], selectcolor=self.colors['bg_secondary'],
                          command=self.on_distributed_mode_changed)
            self.master_radio.pack(side=tk.LEFT, padx=10)
            self.master_radio.pack_forget()  # Hide but keep functionality
            
            self.fleet_radio = tk.Radiobutton(mode_frame, text="Fleet", variable=self.distributed_mode, value="fleet",
                          bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                          font=self.fonts['body'], selectcolor=self.colors['bg_secondary'],
                          command=self.on_distributed_mode_changed)
            self.fleet_radio.pack(side=tk.LEFT, padx=10)
            self.fleet_radio.pack_forget()  # Hide but keep functionality
            
            # Network configuration (for Fleet mode)
            network_frame = tk.Frame(distributed_frame, bg=self.colors['bg_secondary'])
            network_frame.pack(fill=tk.X, pady=5)
            
            tk.Label(network_frame, text="Master IP:", width=10, anchor=tk.W,
                    bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                    font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
            
            master_ip_entry = tk.Entry(network_frame, textvariable=self.master_host, width=15,
                                      font=self.fonts['body'], bg=self.colors['bg_secondary'],
                                      fg=self.colors['text_primary'])
            master_ip_entry.pack(side=tk.LEFT, padx=5)
            
            tk.Label(network_frame, text="UDP:", width=5, anchor=tk.W,
                    bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                    font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
            
            udp_port_entry = tk.Entry(network_frame, textvariable=self.master_udp_port, width=8,
                                     font=self.fonts['body'], bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'])
            udp_port_entry.pack(side=tk.LEFT, padx=2)
            
            tk.Label(network_frame, text="TCP:", width=5, anchor=tk.W,
                    bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                    font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
            
            tcp_port_entry = tk.Entry(network_frame, textvariable=self.master_tcp_port, width=8,
                                     font=self.fonts['body'], bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'])
            tcp_port_entry.pack(side=tk.LEFT, padx=2)
            
            # Fleet status display
            self.fleet_status_label = tk.Label(
                distributed_frame,
                text="Mode: Local - No distributed features active",
                wraplength=700,
                anchor=tk.W,
                fg=self.colors['text_secondary'],
                bg=self.colors['bg_secondary'],
                font=self.fonts['small']
            )
            self.fleet_status_label.pack(fill=tk.X, pady=5)
            
            # Initially hide network config (only show for Fleet mode)
            network_frame.pack_forget()
            
            # Store references for show/hide
            self.distributed_network_frame = network_frame
        
        # Initialize passthrough state
        self.passthrough_active = False
        self.passthrough_thread = None
        self.passthrough_streams = []
        self.pyaudio_capture_stream = None  # Store PyAudio capture stream reference for quick stopping
        
        # Audio device selection frame
        device_frame = ttk.LabelFrame(scrollable_frame, text="🔊 Output Devices", padding=15)
        device_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Device 1 selection
        device1_frame = tk.Frame(device_frame, bg=self.colors['bg_secondary'])
        device1_frame.pack(fill=tk.X, pady=8)
        
        tk.Label(device1_frame, text="Device 1:", width=12, anchor=tk.W, 
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.device1_combo = ttk.Combobox(device1_frame, state="readonly", width=35, font=self.fonts['body'])
        self.device1_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.device1_combo.bind("<<ComboboxSelected>>", self.on_device1_selected)
        
        # Latency adjustment for Device 1
        tk.Label(device1_frame, text="Latency:", width=10, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.device1_latency_var = tk.DoubleVar(value=0.0)
        self.device1_latency_spinbox = tk.Spinbox(
            device1_frame,
            from_=-500.0,
            to=500.0,
            increment=10.0,
            textvariable=self.device1_latency_var,
            width=8,
            font=self.fonts['body'],
            command=self.on_device1_latency_changed,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        )
        self.device1_latency_spinbox.pack(side=tk.LEFT, padx=2)
        self.device1_latency_spinbox.bind('<Return>', lambda e: self.on_device1_latency_changed())
        self.device1_latency_spinbox.bind('<FocusOut>', lambda e: self.on_device1_latency_changed())
        
        tk.Label(device1_frame, text="ms", width=3, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                font=self.fonts['small']).pack(side=tk.LEFT, padx=2)
        
        self.device1_latency_label = tk.Label(device1_frame, text="(auto: 0ms)", width=14, anchor=tk.W, 
                                              fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                                              font=self.fonts['small'])
        self.device1_latency_label.pack(side=tk.LEFT, padx=5)
        
        refresh_btn1 = tk.Button(device1_frame, text="🔄", command=self.refresh_audio_devices_ui,
                                bg=self.colors['accent_primary'], fg=self.colors['text_light'],
                                font=self.fonts['small'], width=3, relief=tk.FLAT, cursor='hand2',
                                activebackground=self.colors['hover_primary'], bd=0, highlightthickness=0, padx=5, pady=3)
        refresh_btn1.pack(side=tk.LEFT, padx=5)
        
        # Device 2 selection
        device2_frame = tk.Frame(device_frame, bg=self.colors['bg_secondary'])
        device2_frame.pack(fill=tk.X, pady=8)
        
        tk.Label(device2_frame, text="Device 2:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.device2_combo = ttk.Combobox(device2_frame, state="readonly", width=35, font=self.fonts['body'])
        self.device2_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.device2_combo.bind("<<ComboboxSelected>>", self.on_device2_selected)
        
        # Latency adjustment for Device 2
        tk.Label(device2_frame, text="Latency:", width=10, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.device2_latency_var = tk.DoubleVar(value=0.0)
        self.device2_latency_spinbox = tk.Spinbox(
            device2_frame,
            from_=-500.0,
            to=500.0,
            increment=10.0,
            textvariable=self.device2_latency_var,
            width=8,
            font=self.fonts['body'],
            command=self.on_device2_latency_changed,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        )
        self.device2_latency_spinbox.pack(side=tk.LEFT, padx=2)
        self.device2_latency_spinbox.bind('<Return>', lambda e: self.on_device2_latency_changed())
        self.device2_latency_spinbox.bind('<FocusOut>', lambda e: self.on_device2_latency_changed())
        
        tk.Label(device2_frame, text="ms", width=3, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                font=self.fonts['small']).pack(side=tk.LEFT, padx=2)
        
        self.device2_latency_label = tk.Label(device2_frame, text="(auto: 0ms)", width=14, anchor=tk.W,
                                              fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                                              font=self.fonts['small'])
        self.device2_latency_label.pack(side=tk.LEFT, padx=5)
        refresh_btn2 = tk.Button(device2_frame, text="🔄", command=self.refresh_audio_devices_ui,
                                bg=self.colors['accent_primary'], fg=self.colors['text_light'],
                                font=self.fonts['small'], width=3, relief=tk.FLAT, cursor='hand2',
                                activebackground=self.colors['hover_primary'], bd=0, highlightthickness=0, padx=5, pady=3)
        refresh_btn2.pack(side=tk.LEFT, padx=5)
        
        # Dynamic device management: +/- buttons to add/remove devices
        device_control_frame = tk.Frame(device_frame, bg=self.colors['bg_secondary'])
        device_control_frame.pack(fill=tk.X, pady=10)
        
        tk.Label(device_control_frame, text="Manage Devices:", width=15, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        
        # Device count label
        self.device_count_label = tk.Label(device_control_frame, text="2 devices",
                                           bg=self.colors['bg_secondary'], fg=self.colors['accent_primary'],
                                           font=self.fonts['body'], width=10)
        self.device_count_label.pack(side=tk.LEFT, padx=5)
        
        # - button to remove device
        remove_device_btn = tk.Button(device_control_frame, text="➖ Remove Device", 
                                      command=self.remove_device,
                                      bg=self.colors['accent_danger'], fg=self.colors['text_light'],
                                      font=self.fonts['body'], relief=tk.FLAT, cursor='hand2',
                                      activebackground='#c0392b', bd=0, highlightthickness=0, 
                                      padx=10, pady=5)
        remove_device_btn.pack(side=tk.LEFT, padx=5)
        
        # + button to add device
        add_device_btn = tk.Button(device_control_frame, text="➕ Add Device",
                                   command=self.add_device,
                                   bg=self.colors['accent_success'], fg=self.colors['text_light'],
                                   font=self.fonts['body'], relief=tk.FLAT, cursor='hand2',
                                   activebackground='#27ae60', bd=0, highlightthickness=0,
                                   padx=10, pady=5)
        add_device_btn.pack(side=tk.LEFT, padx=5)
        
        # Measure all devices (latency) - speeds up passthrough start when many speakers are added
        measure_all_btn = tk.Button(device_control_frame, text="📏 Measure All",
                                    command=self.measure_all_devices,
                                    bg=self.colors['accent_primary'], fg=self.colors['text_light'],
                                    font=self.fonts['body'], relief=tk.FLAT, cursor='hand2',
                                    activebackground='#2980b9', bd=0, highlightthickness=0,
                                    padx=10, pady=5)
        measure_all_btn.pack(side=tk.LEFT, padx=5)
        
        # Container for additional devices (will be populated dynamically)
        self.additional_devices_frame = tk.Frame(device_frame, bg=self.colors['bg_secondary'])
        self.additional_devices_frame.pack(fill=tk.X, pady=5)
        
        # Initialize device tracking
        self.device_widgets = []  # List of (device_frame, combo, latency_var, latency_label, volume_var, volume_label)
        self.num_devices = 2  # Start with 2 devices
        
        # Update device dropdowns
        self.update_device_combos()
        
        # Volume controls frame (moved below output devices)
        volume_frame = ttk.LabelFrame(scrollable_frame, text="🔉 Volume Controls", padding=15)
        volume_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Device 1 volume
        vol1_frame = tk.Frame(volume_frame, bg=self.colors['bg_secondary'])
        vol1_frame.pack(fill=tk.X, pady=8)
        tk.Label(vol1_frame, text="Device 1:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.volume1_var = tk.DoubleVar(value=100.0)
        self.volume1_scale = tk.Scale(
            vol1_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.volume1_var,
            command=self.on_volume1_changed,
            length=400,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            troughcolor=self.colors['border'],
            activebackground=self.colors['accent_primary'],
            highlightthickness=0,
            font=self.fonts['small']
        )
        self.volume1_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.volume1_label = tk.Label(vol1_frame, text="100%", width=8,
                                      bg=self.colors['bg_secondary'], fg=self.colors['accent_primary'],
                                      font=self.fonts['body'])
        self.volume1_label.pack(side=tk.LEFT, padx=5)
        
        # Device 2 volume
        vol2_frame = tk.Frame(volume_frame, bg=self.colors['bg_secondary'])
        vol2_frame.pack(fill=tk.X, pady=8)
        tk.Label(vol2_frame, text="Device 2:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.volume2_var = tk.DoubleVar(value=100.0)
        self.volume2_scale = tk.Scale(
            vol2_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.volume2_var,
            command=self.on_volume2_changed,
            length=400,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            troughcolor=self.colors['border'],
            activebackground=self.colors['accent_primary'],
            highlightthickness=0,
            font=self.fonts['small']
        )
        self.volume2_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.volume2_label = tk.Label(vol2_frame, text="100%", width=8,
                                      bg=self.colors['bg_secondary'], fg=self.colors['accent_primary'],
                                      font=self.fonts['body'])
        self.volume2_label.pack(side=tk.LEFT, padx=5)
        
        # Initialize volume cache with current GUI values (if not already initialized)
        if not hasattr(self, '_volume_cache_lock'):
            self._volume_cache_lock = threading.Lock()
        if not hasattr(self, '_volume_cache'):
            with self._volume_cache_lock:
                self._volume_cache = {1: 1.0, 2: 1.0}  # Initialize to 100%
        
    
    def setup_streaming_tab(self, parent):
        """Set up the SoundCloud streaming tab."""
        # Configure parent frame background
        parent.configure(style='TFrame')
        
        # Create scrollable canvas with scrollbar
        canvas = tk.Canvas(parent, bg=self.colors['bg_primary'], highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                                 bg=self.colors['bg_secondary'], troughcolor=self.colors['bg_dark'],
                                 activebackground=self.colors['accent_primary'])
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg_primary'])
        
        def update_scrollregion(event=None):
            """Update the scroll region to include all content."""
            canvas.update_idletasks()
            scrollable_frame.update_idletasks()
            # Get the actual required size of the scrollable frame
            req_width = scrollable_frame.winfo_reqwidth()
            req_height = scrollable_frame.winfo_reqheight()
            
            # Also check bbox as fallback
            bbox = canvas.bbox("all")
            if bbox:
                # Use the maximum of required height and bbox height, plus padding
                max_height = max(req_height, bbox[3]) + 50  # Extra padding for safety
                max_width = max(req_width, bbox[2]) + 20
                canvas.configure(scrollregion=(0, 0, max_width, max_height))
            elif req_height > 0:
                # Fallback to required size if bbox is not available
                canvas.configure(scrollregion=(0, 0, req_width + 20, req_height + 50))
            else:
                canvas.configure(scrollregion=(0, 0, 0, 0))
        
        def configure_canvas_width(event):
            """Configure canvas window width to match canvas width."""
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            # Update scroll region when canvas is resized
            parent.after(10, update_scrollregion)
        
        # Update scroll region whenever scrollable frame changes
        scrollable_frame.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        canvas.bind("<Configure>", configure_canvas_width)
        # Also update on window resize
        parent.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Update scroll region multiple times to ensure all content is captured
        parent.after(50, update_scrollregion)
        parent.after(100, update_scrollregion)
        parent.after(200, update_scrollregion)
        parent.after(500, update_scrollregion)  # One more delayed update
        
        # Search frame
        search_frame = ttk.LabelFrame(scrollable_frame, text="🔍 Search SoundCloud", padding=15)
        search_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Info label about flexible search
        info_label = tk.Label(
            search_frame,
            text="💡 Tip: You don't need the exact song name! Try partial names, artist names, or keywords.",
            fg=self.colors['accent_primary'],
            bg=self.colors['bg_secondary'],
            font=self.fonts['small'],
            wraplength=700,
            justify=tk.LEFT
        )
        info_label.pack(anchor=tk.W, pady=(0, 10))
        
        search_entry_frame = tk.Frame(search_frame, bg=self.colors['bg_secondary'])
        search_entry_frame.pack(fill=tk.X, pady=5)
        
        self.search_entry = tk.Entry(search_entry_frame, font=self.fonts['body'],
                                     bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                                     relief=tk.FLAT, bd=2, highlightthickness=1,
                                     highlightcolor=self.colors['accent_primary'],
                                     highlightbackground=self.colors['border'])
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, ipady=5)
        self.search_entry.bind('<Return>', lambda e: self.search_tracks())
        
        search_btn = tk.Button(
            search_entry_frame,
            text="🔍 Search",
            command=self.search_tracks,
            width=12,
            bg=self.colors['accent_primary'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_primary'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        search_btn.pack(side=tk.LEFT, padx=5)
        
        # Audio device selection frame (for SoundCloud tab)
        device_frame_sc = ttk.LabelFrame(scrollable_frame, text="🔊 Output Devices", padding=15)
        device_frame_sc.pack(fill=tk.X, padx=15, pady=10)
        
        # Device 1 selection
        device1_frame_sc = tk.Frame(device_frame_sc, bg=self.colors['bg_secondary'])
        device1_frame_sc.pack(fill=tk.X, pady=8)
        
        tk.Label(device1_frame_sc, text="Device 1:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.device1_combo_sc = ttk.Combobox(device1_frame_sc, state="readonly", width=35, font=self.fonts['body'])
        self.device1_combo_sc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.device1_combo_sc.bind("<<ComboboxSelected>>", self.on_device1_selected_sc)
        
        # Latency adjustment for Device 1 (SoundCloud tab - syncs with local tab)
        tk.Label(device1_frame_sc, text="Latency:", width=10, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        # Note: We'll reuse the same variables from local tab, but need to sync the spinbox
        self.device1_latency_spinbox_sc = tk.Spinbox(
            device1_frame_sc,
            from_=-500.0,
            to=500.0,
            increment=10.0,
            textvariable=self.device1_latency_var,
            width=8,
            font=self.fonts['body'],
            command=self.on_device1_latency_changed,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        )
        self.device1_latency_spinbox_sc.pack(side=tk.LEFT, padx=2)
        self.device1_latency_spinbox_sc.bind('<Return>', lambda e: self.on_device1_latency_changed())
        self.device1_latency_spinbox_sc.bind('<FocusOut>', lambda e: self.on_device1_latency_changed())
        
        tk.Label(device1_frame_sc, text="ms", width=3, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                font=self.fonts['small']).pack(side=tk.LEFT, padx=2)
        
        self.device1_latency_label_sc = tk.Label(device1_frame_sc, text="(auto: 0ms)", width=14, anchor=tk.W,
                                                  fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                                                  font=self.fonts['small'])
        self.device1_latency_label_sc.pack(side=tk.LEFT, padx=5)
        
        # Device 2 selection
        device2_frame_sc = tk.Frame(device_frame_sc, bg=self.colors['bg_secondary'])
        device2_frame_sc.pack(fill=tk.X, pady=8)
        
        tk.Label(device2_frame_sc, text="Device 2:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        self.device2_combo_sc = ttk.Combobox(device2_frame_sc, state="readonly", width=35, font=self.fonts['body'])
        self.device2_combo_sc.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.device2_combo_sc.bind("<<ComboboxSelected>>", self.on_device2_selected_sc)
        
        # Latency adjustment for Device 2 (SoundCloud tab - syncs with local tab)
        tk.Label(device2_frame_sc, text="Latency:", width=10, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        # Note: We'll reuse the same variables from local tab, but need to sync the spinbox
        self.device2_latency_spinbox_sc = tk.Spinbox(
            device2_frame_sc,
            from_=-500.0,
            to=500.0,
            increment=10.0,
            textvariable=self.device2_latency_var,
            width=8,
            font=self.fonts['body'],
            command=self.on_device2_latency_changed,
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        )
        self.device2_latency_spinbox_sc.pack(side=tk.LEFT, padx=2)
        self.device2_latency_spinbox_sc.bind('<Return>', lambda e: self.on_device2_latency_changed())
        self.device2_latency_spinbox_sc.bind('<FocusOut>', lambda e: self.on_device2_latency_changed())
        
        tk.Label(device2_frame_sc, text="ms", width=3, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                font=self.fonts['small']).pack(side=tk.LEFT, padx=2)
        
        self.device2_latency_label_sc = tk.Label(device2_frame_sc, text="(auto: 0ms)", width=14, anchor=tk.W,
                                                  fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                                                  font=self.fonts['small'])
        self.device2_latency_label_sc.pack(side=tk.LEFT, padx=5)
        
        # Update device dropdowns
        self.update_device_combos_sc()
        
        # Results frame
        results_frame = ttk.LabelFrame(scrollable_frame, text="📋 Search Results", padding=15)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Listbox with scrollbar
        listbox_frame = tk.Frame(results_frame, bg=self.colors['bg_secondary'])
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(listbox_frame, bg=self.colors['bg_secondary'],
                                troughcolor=self.colors['border'], activebackground=self.colors['accent_primary'])
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.results_listbox = tk.Listbox(
            listbox_frame,
            yscrollcommand=scrollbar.set,
            font=self.fonts['body'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            selectbackground=self.colors['accent_primary'],
            selectforeground=self.colors['text_light'],
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0
        )
        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.results_listbox.bind('<Double-Button-1>', lambda e: self.play_selected_track())
        scrollbar.config(command=self.results_listbox.yview)
        
        # Play and Add to Playlist buttons
        button_frame = tk.Frame(results_frame, bg=self.colors['bg_secondary'])
        button_frame.pack(pady=10)
        
        play_selected_btn = tk.Button(
            button_frame,
            text="▶ Play Selected",
            command=self.play_selected_track,
            bg=self.colors['accent_success'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=18,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_success'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        play_selected_btn.pack(side=tk.LEFT, padx=8)
        
        add_to_playlist_btn = tk.Button(
            button_frame,
            text="➕ Add to Playlist",
            command=self.add_selected_to_playlist,
            bg=self.colors['accent_primary'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=18,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_primary'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        add_to_playlist_btn.pack(side=tk.LEFT, padx=8)
        
        self.search_results = []
    
    def setup_playlist_tab(self, parent):
        """Set up the playlist tab."""
        # Configure parent frame background
        parent.configure(style='TFrame')
        
        # Create scrollable canvas with scrollbar
        canvas = tk.Canvas(parent, bg=self.colors['bg_primary'], highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                                 bg=self.colors['bg_secondary'], troughcolor=self.colors['bg_dark'],
                                 activebackground=self.colors['accent_primary'])
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg_primary'])
        
        def update_scrollregion(event=None):
            """Update the scroll region to include all content."""
            canvas.update_idletasks()
            scrollable_frame.update_idletasks()
            # Get the actual required size of the scrollable frame
            req_width = scrollable_frame.winfo_reqwidth()
            req_height = scrollable_frame.winfo_reqheight()
            
            # Also check bbox as fallback
            bbox = canvas.bbox("all")
            if bbox:
                # Use the maximum of required height and bbox height, plus padding
                max_height = max(req_height, bbox[3]) + 50  # Extra padding for safety
                max_width = max(req_width, bbox[2]) + 20
                canvas.configure(scrollregion=(0, 0, max_width, max_height))
            elif req_height > 0:
                # Fallback to required size if bbox is not available
                canvas.configure(scrollregion=(0, 0, req_width + 20, req_height + 50))
            else:
                canvas.configure(scrollregion=(0, 0, 0, 0))
        
        def configure_canvas_width(event):
            """Configure canvas window width to match canvas width."""
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            # Update scroll region when canvas is resized
            parent.after(10, update_scrollregion)
        
        # Update scroll region whenever scrollable frame changes
        scrollable_frame.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        canvas.bind("<Configure>", configure_canvas_width)
        # Also update on window resize
        parent.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Update scroll region multiple times to ensure all content is captured
        parent.after(50, update_scrollregion)
        parent.after(100, update_scrollregion)
        parent.after(200, update_scrollregion)
        parent.after(500, update_scrollregion)  # One more delayed update
        
        # Playlist listbox
        playlist_frame = ttk.LabelFrame(scrollable_frame, text="Playlist", padding=10)
        playlist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Listbox with scrollbar
        listbox_frame = tk.Frame(playlist_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.playlist_listbox = tk.Listbox(
            listbox_frame,
            yscrollcommand=scrollbar.set,
            font=("Arial", 9),
            selectmode=tk.SINGLE
        )
        self.playlist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.playlist_listbox.bind('<Double-Button-1>', lambda e: self.play_playlist_item())
        scrollbar.config(command=self.playlist_listbox.yview)
        
        # Playlist controls
        controls_frame = tk.Frame(playlist_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        # Add buttons
        add_local_btn = tk.Button(
            controls_frame,
            text="Add Local File",
            command=self.add_local_to_playlist,
            width=15
        )
        add_local_btn.pack(side=tk.LEFT, padx=2)
        
        add_soundcloud_btn = tk.Button(
            controls_frame,
            text="Add from SoundCloud",
            command=self.add_soundcloud_to_playlist,
            width=18,
            state=tk.NORMAL if STREAMING_AVAILABLE else tk.DISABLED
        )
        add_soundcloud_btn.pack(side=tk.LEFT, padx=2)
        
        remove_btn = tk.Button(
            controls_frame,
            text="Remove Selected",
            command=self.remove_from_playlist,
            width=15
        )
        remove_btn.pack(side=tk.LEFT, padx=2)
        
        clear_btn = tk.Button(
            controls_frame,
            text="Clear All",
            command=self.clear_playlist,
            width=15
        )
        clear_btn.pack(side=tk.LEFT, padx=2)
        
        # Reorder buttons
        reorder_frame = tk.Frame(playlist_frame, bg=self.colors['bg_secondary'])
        reorder_frame.pack(fill=tk.X, pady=10)
        
        move_up_btn = tk.Button(
            reorder_frame,
            text="⬆ Move Up",
            command=self.move_playlist_item_up,
            width=16,
            bg=self.colors['accent_primary'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_primary'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        move_up_btn.pack(side=tk.LEFT, padx=5)
        
        move_down_btn = tk.Button(
            reorder_frame,
            text="⬇ Move Down",
            command=self.move_playlist_item_down,
            width=16,
            bg=self.colors['accent_primary'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_primary'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        move_down_btn.pack(side=tk.LEFT, padx=5)
        
        # Playlist playback controls
        playback_frame = tk.Frame(playlist_frame, bg=self.colors['bg_secondary'])
        playback_frame.pack(fill=tk.X, pady=10)
        
        self.play_playlist_btn = tk.Button(
            playback_frame,
            text="▶ Play Playlist",
            command=self.play_playlist,
            bg=self.colors['accent_success'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=16,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_success'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        self.play_playlist_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_playlist_btn = tk.Button(
            playback_frame,
            text="⏸ Pause",
            command=self.pause_playlist,
            bg=self.colors['accent_warning'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=14,
            state=tk.DISABLED,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground='#E67E22',
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        self.pause_playlist_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_playlist_btn = tk.Button(
            playback_frame,
            text="⏹ Stop",
            command=self.stop_playlist,
            bg=self.colors['accent_danger'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            width=14,
            state=tk.DISABLED,
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_danger'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        self.stop_playlist_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_playlist_btn = tk.Button(
            playback_frame,
            text="⏭ Next",
            command=self.next_playlist_item,
            width=14,
            bg=self.colors['accent_primary'],
            fg=self.colors['text_light'],
            font=self.fonts['button'],
            relief=tk.FLAT,
            cursor='hand2',
            activebackground=self.colors['hover_primary'],
            activeforeground=self.colors['text_light'],
            bd=0,
            padx=10,
            pady=5
        )
        self.next_playlist_btn.pack(side=tk.LEFT, padx=5)
        
        # Current playing indicator
        self.playlist_status_label = tk.Label(
            playlist_frame,
            text="📋 Playlist is empty",
            fg=self.colors['text_secondary'],
            bg=self.colors['bg_secondary'],
            font=self.fonts['body']
        )
        self.playlist_status_label.pack(pady=10)
        
        # Update playlist display
        self.update_playlist_display()
    
    def setup_help_tab(self, parent):
        """Set up the help tab."""
        # Configure parent frame background
        parent.configure(style='TFrame')
        
        # Create scrollable canvas with scrollbar
        canvas = tk.Canvas(parent, bg=self.colors['bg_primary'], highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview,
                                 bg=self.colors['bg_secondary'], troughcolor=self.colors['bg_dark'],
                                 activebackground=self.colors['accent_primary'])
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg_primary'])
        
        def update_scrollregion(event=None):
            """Update the scroll region to include all content."""
            canvas.update_idletasks()
            scrollable_frame.update_idletasks()
            # Get the actual required size of the scrollable frame
            req_width = scrollable_frame.winfo_reqwidth()
            req_height = scrollable_frame.winfo_reqheight()
            
            # Also check bbox as fallback
            bbox = canvas.bbox("all")
            if bbox:
                # Use the maximum of required height and bbox height, plus padding
                max_height = max(req_height, bbox[3]) + 50  # Extra padding for safety
                max_width = max(req_width, bbox[2]) + 20
                canvas.configure(scrollregion=(0, 0, max_width, max_height))
            elif req_height > 0:
                # Fallback to required size if bbox is not available
                canvas.configure(scrollregion=(0, 0, req_width + 20, req_height + 50))
            else:
                canvas.configure(scrollregion=(0, 0, 0, 0))
        
        def configure_canvas_width(event):
            """Configure canvas window width to match canvas width."""
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)
            # Update scroll region when canvas is resized
            parent.after(10, update_scrollregion)
        
        # Update scroll region whenever scrollable frame changes
        scrollable_frame.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        canvas.bind("<Configure>", configure_canvas_width)
        # Also update on window resize
        parent.bind("<Configure>", lambda e: parent.after(10, update_scrollregion))
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Update scroll region multiple times to ensure all content is captured
        parent.after(50, update_scrollregion)
        parent.after(100, update_scrollregion)
        parent.after(200, update_scrollregion)
        parent.after(500, update_scrollregion)  # One more delayed update
        
        help_text = """
HOW TO PLAY AUDIO TO MULTIPLE DEVICES ON WINDOWS

Method 1: Enable Stereo Mix (Easiest)
--------------------------------------
1. Right-click the speaker icon in your system tray
2. Select 'Sounds' or 'Sound settings'
3. Go to the 'Recording' tab
4. Right-click in an empty area and check 'Show Disabled Devices'
5. Find 'Stereo Mix' and right-click it, then select 'Enable'
6. Right-click 'Stereo Mix' again and select 'Properties'
7. Go to the 'Listen' tab
8. Check 'Listen to this device'
9. Select your second audio device from the dropdown
10. Click OK

Now audio will play to both devices simultaneously!

Method 2: Use Audio Mirroring
-------------------------------
1. Open Windows Settings (Win + I)
2. Go to System > Sound
3. Under 'Advanced sound options', click 'App volume and device preferences'
4. Configure different apps to use different output devices

Method 3: Use Third-Party Software
------------------------------------
Consider using:
- VoiceMeeter (free virtual audio mixer)
- Audio Router (free Windows app)
- CheVolume (paid but powerful)

These tools make multi-device audio much easier!
        """
        
        text_widget = tk.Text(scrollable_frame, wrap=tk.WORD, padx=10, pady=10, 
                             font=("Arial", 9), bg=self.colors['bg_secondary'], 
                             fg=self.colors['text_primary'], insertbackground=self.colors['accent_primary'],
                             selectbackground=self.colors['accent_primary'], 
                             selectforeground=self.colors['text_light'])
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert('1.0', help_text)
        text_widget.config(state=tk.DISABLED)
    
    def search_tracks(self):
        """Search for tracks on SoundCloud."""
        if not self.streaming_manager:
            messagebox.showwarning(
                "Streaming Unavailable",
                "SoundCloud streaming is not properly configured.\n"
                "Make sure you have installed: yt-dlp requests\n\n"
                "Run: pip install yt-dlp requests"
            )
            return
        
        if not self.streaming_manager.soundcloud.available:
            messagebox.showerror(
                "SoundCloud Not Available",
                "SoundCloud service is not available.\n\n"
                "Please check the console for error messages."
            )
            return
        
        # Check if yt-dlp is available
        if not self.streaming_manager.soundcloud.ytdlp_available:
            import sys
            error_msg = (
                "yt-dlp is required for SoundCloud search but is not installed!\n\n"
                f"Python executable: {sys.executable}\n\n"
                "To fix this:\n"
                "1. Open a terminal/command prompt\n"
                f"2. Run: {sys.executable} -m pip install yt-dlp\n"
                "   OR simply: pip install yt-dlp\n\n"
                "3. Restart this application\n\n"
                "You can also double-click 'install_ytdlp.bat' to install it automatically."
            )
            messagebox.showerror("yt-dlp Not Installed", error_msg)
            return
        
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Search Error", "Please enter a search query.")
            return
        
        # Basic query validation (sanitize to prevent injection)
        if len(query) > 500:
            messagebox.showwarning("Search Error", "Search query is too long (max 500 characters).")
            return
        
        self.status_label.config(text=f"Searching SoundCloud for '{query}'...", fg="blue")
        self.results_listbox.delete(0, tk.END)
        self.search_results = []
        
        def search_thread():
            try:
                print(f"\n=== Starting SoundCloud search for: '{query}' ===")
                results = self.streaming_manager.search(query)
                print(f"=== Search completed. Found {len(results)} results ===\n")
                
                self.search_results = results
                
                self.root.after(0, lambda: self.update_search_results(results))
                
            except Exception as e:
                error_msg = str(e)
                print(f"Search exception: {error_msg}")
                import traceback
                traceback.print_exc()
                
                self.root.after(0, lambda: messagebox.showerror(
                    "Search Error",
                    f"Error searching SoundCloud:\n\n{error_msg}\n\n"
                    "Check the console for more details."
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text="Search failed - check console", fg="red"
                ))
        
        thread = threading.Thread(target=search_thread, daemon=True)
        thread.start()
    
    def update_search_results(self, results):
        """Update the search results listbox."""
        self.results_listbox.delete(0, tk.END)
        
        if not results:
            self.status_label.config(
                text="No results found. Try different keywords or check console for errors.",
                fg="orange"
            )
            messagebox.showinfo(
                "No Results",
                "No tracks found on SoundCloud.\n\n"
                "Try:\n"
                "- Different keywords\n"
                "- Artist names\n"
                "- Partial song names\n\n"
                "Check the console for any error messages."
            )
            return
        
        for track in results:
            display_text = f"{track['artist']} - {track['title']}"
            self.results_listbox.insert(tk.END, display_text)
        
        self.status_label.config(
            text=f"Found {len(results)} results from SoundCloud (sorted by relevance)",
            fg="green"
        )
    
    def add_selected_to_playlist(self):
        """Add the selected SoundCloud track to the playlist."""
        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select a track from the list.")
            return
        
        index = selection[0]
        if index >= len(self.search_results):
            return
        
        track = self.search_results[index]
        
        # Add to playlist
        self.playlist.append({
            'type': 'streaming',
            'path': track.get('url', ''),
            'title': track.get('title', 'Unknown'),
            'artist': track.get('artist', 'Unknown'),
            'track_info': track
        })
        
        # Update playlist display if playlist tab exists
        if hasattr(self, 'playlist_listbox'):
            self.update_playlist_display()
        
        self.status_label.config(text=f"Added '{track.get('title', 'Unknown')}' to playlist", fg="green")
    
    def play_selected_track(self):
        """Play the selected track from search results."""
        selection = self.results_listbox.curselection()
        if not selection:
            messagebox.showwarning("Selection Error", "Please select a track from the list.")
            return
        
        index = selection[0]
        if index >= len(self.search_results):
            return
        
        track = self.search_results[index]
        
        self.status_label.config(text=f"Downloading {track['title']}...", fg="blue")
        self.play_btn.config(state=tk.DISABLED)
        
        def download_and_play():
            try:
                audio_file = self.streaming_manager.get_audio_file(track)
                
                if not audio_file or not os.path.exists(audio_file):
                    raise Exception("Failed to download track")
                
                self.root.after(0, lambda: self.play_streamed_audio(audio_file, track['title']))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Playback Error",
                    f"Error downloading/playing track: {str(e)}"
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text="Error occurred", fg="red"
                ))
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
        
        thread = threading.Thread(target=download_and_play, daemon=True)
        thread.start()
    
    def play_streamed_audio(self, audio_file, track_name):
        """Play a streamed audio file."""
        self.audio_file_path = audio_file
        self.file_label.config(text=f"Playing: {track_name}")
        self.status_label.config(text="Loading audio...", fg="blue")
        self.stop_btn.config(state=tk.NORMAL)
        
        def play_thread():
            try:
                # Stop any existing player first
                if self.player:
                    self.player.stop()
                    time.sleep(0.1)  # Brief pause to ensure cleanup
                
                # Create player with selected devices from SoundCloud tab
                device1_name = "None" if self.device1_index is None else next((d['name'] for d in self.audio_devices if d['index'] == self.device1_index), f"Unknown (index: {self.device1_index})")
                device2_name = "None" if self.device2_index is None else next((d['name'] for d in self.audio_devices if d['index'] == self.device2_index), f"Unknown (index: {self.device2_index})")
                print(f"Creating player:")
                print(f"  Device 1: {device1_name} (index: {self.device1_index})")
                print(f"  Device 2: {device2_name} (index: {self.device2_index})")
                self.player = SynchronizedAudioPlayer(
                    device1=self.device1_index,
                    device2=self.device2_index,
                    device1_latency_adjustment=self.device1_latency_adjustment / 1000.0,  # Convert ms to seconds
                    device2_latency_adjustment=self.device2_latency_adjustment / 1000.0   # Convert ms to seconds
                )
                # Set volumes
                self.player.set_volume(1, self.volume1_var.get() / 100.0)
                self.player.set_volume(2, self.volume2_var.get() / 100.0)
                self.player.load_audio_file(self.audio_file_path)
                
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Playing: {track_name}", fg="green"
                ))
                
                self.player.play()
                
                self.root.after(0, lambda: self.status_label.config(
                    text="Playback completed", fg="gray"
                ))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Playback Error",
                    f"Error during playback: {str(e)}"
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text="Error occurred", fg="red"
                ))
            finally:
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.pause_btn.config(text="Pause", state=tk.DISABLED))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        
        thread = threading.Thread(target=play_thread, daemon=True)
        thread.start()
    
    def browse_audio_file(self):
        """Open file dialog to select an audio file."""
        file_path = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            # Validate the selected file
            is_valid, error_msg = validate_audio_file(file_path)
            if not is_valid:
                messagebox.showerror("Invalid Audio File", error_msg)
                return
            
            self.audio_file_path = file_path
            filename = os.path.basename(file_path)
            self.file_label.config(text=f"Selected: {filename}")
            self.status_label.config(text="Ready to play", fg="green")
    
    def add_current_file_to_playlist(self):
        """Add the currently selected local file to the playlist."""
        if not self.audio_file_path or not os.path.exists(self.audio_file_path):
            messagebox.showwarning("No File", "Please select an audio file first.")
            return
        
        self.playlist.append({
            'type': 'local',
            'path': self.audio_file_path,
            'title': os.path.basename(self.audio_file_path),
            'artist': 'Local File'
        })
        
        # Update playlist display if playlist tab exists
        if hasattr(self, 'playlist_listbox'):
            self.update_playlist_display()
        
        self.status_label.config(text=f"Added '{os.path.basename(self.audio_file_path)}' to playlist", fg="green")
    
    def play_audio(self):
        """Start playing audio."""
        if not self.audio_file_path or not os.path.exists(self.audio_file_path):
            messagebox.showwarning(
                "File Error",
                "Please select a valid audio file or search for a track."
            )
            return
        
        self.play_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Loading audio...", fg="blue")
        
        def play_thread():
            try:
                # Stop any existing player first
                if self.player:
                    self.player.stop()
                    time.sleep(0.1)  # Brief pause to ensure cleanup
                
                # Create player with selected devices from local tab
                device1_name = "None" if self.device1_index is None else next((d['name'] for d in self.audio_devices if d['index'] == self.device1_index), f"Unknown (index: {self.device1_index})")
                device2_name = "None" if self.device2_index is None else next((d['name'] for d in self.audio_devices if d['index'] == self.device2_index), f"Unknown (index: {self.device2_index})")
                print(f"Creating player:")
                print(f"  Device 1: {device1_name} (index: {self.device1_index})")
                print(f"  Device 2: {device2_name} (index: {self.device2_index})")
                self.player = SynchronizedAudioPlayer(
                    device1=self.device1_index,
                    device2=self.device2_index,
                    device1_latency_adjustment=self.device1_latency_adjustment / 1000.0,  # Convert ms to seconds
                    device2_latency_adjustment=self.device2_latency_adjustment / 1000.0   # Convert ms to seconds
                )
                # Set volumes
                self.player.set_volume(1, self.volume1_var.get() / 100.0)
                self.player.set_volume(2, self.volume2_var.get() / 100.0)
                self.player.load_audio_file(self.audio_file_path)
                
                self.root.after(0, lambda: self.status_label.config(
                    text="Playing...", fg="green"
                ))
                
                self.player.play()
                
                self.root.after(0, lambda: self.status_label.config(
                    text="Playback completed", fg="gray"
                ))
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Playback Error",
                    f"Error during playback: {str(e)}"
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text="Error occurred", fg="red"
                ))
            finally:
                self.root.after(0, lambda: self.play_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.pause_btn.config(text="Pause", state=tk.DISABLED))
                self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        
        thread = threading.Thread(target=play_thread, daemon=True)
        thread.start()
    
    def update_device_combos(self):
        """Update device combo boxes for local tab."""
        device_names = ["None (Use Default)"] + [d['name'] for d in self.audio_devices]
        self.device1_combo['values'] = device_names
        self.device2_combo['values'] = device_names
        
        # Set current selections
        if self.device1_index is not None:
            for i, d in enumerate(self.audio_devices):
                if d['index'] == self.device1_index:
                    self.device1_combo.current(i + 1)
                    break
        else:
            self.device1_combo.current(0)
        
        if self.device2_index is not None:
            for i, d in enumerate(self.audio_devices):
                if d['index'] == self.device2_index:
                    self.device2_combo.current(i + 1)
                    break
        else:
            self.device2_combo.current(0)
    
    def update_device_combos_sc(self):
        """Update device combo boxes for SoundCloud tab."""
        if not hasattr(self, 'device1_combo_sc') or not hasattr(self, 'device2_combo_sc'):
            print("SoundCloud device combos not yet created, skipping update")
            return
        
        device_names = ["None (Use Default)"] + [d['name'] for d in self.audio_devices]
        print(f"Updating SoundCloud device combos with {len(device_names)} options")
        
        self.device1_combo_sc['values'] = device_names
        self.device2_combo_sc['values'] = device_names
        
        # Set current selections (sync with local tab)
        if self.device1_index is not None:
            for i, d in enumerate(self.audio_devices):
                if d['index'] == self.device1_index:
                    self.device1_combo_sc.current(i + 1)
                    break
        else:
            self.device1_combo_sc.current(0)
        
        if self.device2_index is not None:
            for i, d in enumerate(self.audio_devices):
                if d['index'] == self.device2_index:
                    self.device2_combo_sc.current(i + 1)
                    break
        else:
            self.device2_combo_sc.current(0)
    
    def refresh_audio_devices_ui(self):
        """Refresh audio devices and update UI."""
        self.refresh_audio_devices()
        self.update_device_combos()
        self.update_device_combos_sc()
        self.status_label.config(text="Audio devices refreshed", fg="green")
    
    def on_device1_selected(self, event=None):
        """Handle device 1 selection in local tab."""
        selection = self.device1_combo.current()
        if selection == 0:  # "None"
            self.device1_index = None
            self.device1_measured_latency = 0.0
            self.device1_latency_label.config(text="(auto: 0ms)", fg="gray")
            self.device1_latency_label_sc.config(text="(auto: 0ms)", fg="gray")
            print("Device 1: None (using default)")
        else:
            device_idx = selection - 1
            if device_idx < len(self.audio_devices):
                device_index = self.audio_devices[device_idx]['index']
                # Validate device index
                is_valid, error_msg = validate_device_index(device_index, self.audio_devices, "Device 1")
                if not is_valid:
                    messagebox.showerror("Invalid Device", error_msg)
                    return
                
                self.device1_index = device_index
                device_name = self.audio_devices[device_idx]['name']
                print(f"Device 1 selected: '{device_name}' (index: {self.device1_index})")
                # Measure latency automatically
                self.measure_device_latency(1, self.device1_index, device_name)
            else:
                error_msg = f"Device index {device_idx} out of range (max: {len(self.audio_devices)-1})"
                print(f"ERROR: {error_msg}")
                messagebox.showerror("Invalid Device Selection", error_msg)
        # Sync with SoundCloud tab
        self.update_device_combos_sc()
    
    def on_device2_selected(self, event=None):
        """Handle device 2 selection in local tab."""
        selection = self.device2_combo.current()
        if selection == 0:  # "None"
            self.device2_index = None
            self.device2_measured_latency = 0.0
            self.device2_latency_label.config(text="(auto: 0ms)", fg="gray")
            self.device2_latency_label_sc.config(text="(auto: 0ms)", fg="gray")
            print("Device 2: None (not used)")
        else:
            device_idx = selection - 1
            if device_idx < len(self.audio_devices):
                device_index = self.audio_devices[device_idx]['index']
                # Validate device index
                is_valid, error_msg = validate_device_index(device_index, self.audio_devices, "Device 2")
                if not is_valid:
                    messagebox.showerror("Invalid Device", error_msg)
                    return
                
                self.device2_index = device_index
                device_name = self.audio_devices[device_idx]['name']
                print(f"Device 2 selected: '{device_name}' (index: {self.device2_index})")
                # Measure latency automatically
                self.measure_device_latency(2, self.device2_index, device_name)
            else:
                error_msg = f"Device index {device_idx} out of range (max: {len(self.audio_devices)-1})"
                print(f"ERROR: {error_msg}")
                messagebox.showerror("Invalid Device Selection", error_msg)
        # Sync with SoundCloud tab
        self.update_device_combos_sc()
    
    def on_device1_selected_sc(self, event=None):
        """Handle device 1 selection in SoundCloud tab."""
        selection = self.device1_combo_sc.current()
        if selection == 0:  # "None"
            self.device1_index = None
            self.device1_measured_latency = 0.0
            self.device1_latency_label.config(text="(auto: 0ms)", fg="gray")
            self.device1_latency_label_sc.config(text="(auto: 0ms)", fg="gray")
            print("Device 1: None (using default)")
        else:
            device_idx = selection - 1
            if device_idx < len(self.audio_devices):
                self.device1_index = self.audio_devices[device_idx]['index']
                device_name = self.audio_devices[device_idx]['name']
                print(f"Device 1 selected: '{device_name}' (index: {self.device1_index})")
                # Measure latency automatically
                self.measure_device_latency(1, self.device1_index, device_name)
            else:
                print(f"ERROR: Device index {device_idx} out of range (max: {len(self.audio_devices)-1})")
        # Sync with local tab
        self.update_device_combos()
    
    def on_device2_selected_sc(self, event=None):
        """Handle device 2 selection in SoundCloud tab."""
        selection = self.device2_combo_sc.current()
        if selection == 0:  # "None"
            self.device2_index = None
            self.device2_measured_latency = 0.0
            self.device2_latency_label.config(text="(auto: 0ms)", fg="gray")
            self.device2_latency_label_sc.config(text="(auto: 0ms)", fg="gray")
            print("Device 2: None (not used)")
        else:
            device_idx = selection - 1
            if device_idx < len(self.audio_devices):
                self.device2_index = self.audio_devices[device_idx]['index']
                device_name = self.audio_devices[device_idx]['name']
                print(f"Device 2 selected: '{device_name}' (index: {self.device2_index})")
                # Measure latency automatically
                self.measure_device_latency(2, self.device2_index, device_name)
            else:
                print(f"ERROR: Device index {device_idx} out of range (max: {len(self.audio_devices)-1})")
        # Sync with local tab
        self.update_device_combos()
        
    def on_dynamic_device_selected(self, device_num):
        """Handle selection for a dynamic device (Device 3+)."""
        # Find the widget dict for this device
        widget = None
        for w in self.device_widgets:
            if w['device_num'] == device_num:
                widget = w
                break
        
        if not widget:
            print(f"Error: Could not find widget for Device {device_num}")
            return
            
        selection_text = widget['combo'].get()
        print(f"Device {device_num} selected: '{selection_text}'")
        
        # Parse selection
        if not selection_text or selection_text == "None":
            widget['measured_latency'] = 0.0
            widget['latency_label'].config(text="(auto: 0ms)", fg="gray")
            return
            
        # Get index using helper
        device_idx = self.get_device_index_from_selection(selection_text)
        
        if device_idx is not None:
            # Extract name
            device_name = selection_text.split(" (index:")[0] if " (index:" in selection_text else selection_text
            # Measure latency
            print(f"Measuring latency for Device {device_num}...")
            self.measure_device_latency(device_num, device_idx, device_name)
        else:
            print(f"Could not extract index for Device {device_num}")

    def add_device(self):
        """Add a new device slot dynamically."""
        if self.passthrough_active:
            messagebox.showwarning("Cannot Add Device", "Please stop passthrough before adding devices.")
            return
        
        self.num_devices += 1
        device_num = self.num_devices
        
        # Create device selection frame
        device_frame = tk.Frame(self.additional_devices_frame, bg=self.colors['bg_secondary'])
        device_frame.pack(fill=tk.X, pady=8)
        
        tk.Label(device_frame, text=f"Device {device_num}:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        
        device_combo = ttk.Combobox(device_frame, state="readonly", width=35, font=self.fonts['body'])
        device_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Latency adjustment
        tk.Label(device_frame, text="Latency:", width=10, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        
        latency_var = tk.DoubleVar(value=0.0)
        latency_spinbox = tk.Spinbox(
            device_frame, from_=-500.0, to=500.0, increment=10.0,
            textvariable=latency_var, width=8, font=self.fonts['body'],
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary']
        )
        latency_spinbox.pack(side=tk.LEFT, padx=2)
        
        tk.Label(device_frame, text="ms", width=3, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                font=self.fonts['small']).pack(side=tk.LEFT, padx=2)
        
        latency_label = tk.Label(device_frame, text="(auto: 0ms)", width=14, anchor=tk.W,
                                fg=self.colors['text_secondary'], bg=self.colors['bg_secondary'],
                                font=self.fonts['small'])
        latency_label.pack(side=tk.LEFT, padx=5)
        
        # Create volume control frame
        volume_frame = tk.Frame(self.additional_devices_frame, bg=self.colors['bg_secondary'])
        volume_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(volume_frame, text=f"Device {device_num}:", width=12, anchor=tk.W,
                bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
                font=self.fonts['body']).pack(side=tk.LEFT, padx=5)
        
        volume_var = tk.DoubleVar(value=100.0)
        volume_scale = tk.Scale(
            volume_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=volume_var, length=400,
            bg=self.colors['bg_secondary'], fg=self.colors['text_primary'],
            troughcolor=self.colors['border'], activebackground=self.colors['accent_primary'],
            highlightthickness=0, font=self.fonts['small']
        )
        volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        volume_label = tk.Label(volume_frame, text="100%", width=8,
                               bg=self.colors['bg_secondary'], fg=self.colors['accent_primary'],
                               font=self.fonts['body'])
        volume_label.pack(side=tk.LEFT, padx=5)
        
        # Store widget references
        self.device_widgets.append({
            'device_frame': device_frame,
            'volume_frame': volume_frame,
            'combo': device_combo,
            'latency_var': latency_var,
            'latency_label': latency_label,
            'volume_var': volume_var,
            'volume_label': volume_label,
            'volume_scale': volume_scale,
            'device_num': device_num,
            'measured_latency': 0.0  # Initialize measured latency
        })
        
        # Bind selection event for auto-measurement
        # Use default arg to capture current device_num value in lambda
        device_combo.bind("<<ComboboxSelected>>", lambda e, num=device_num: self.on_dynamic_device_selected(num))
        
        # Update device combos for all devices
        self.update_device_combos()
        
        # Update device count label
        self.device_count_label.config(text=f"{self.num_devices} devices")
        
        print(f"✓ Added Device {device_num}")
    
    def remove_device(self):
        """Remove the last device slot."""
        if self.passthrough_active:
            messagebox.showwarning("Cannot Remove Device", "Please stop passthrough before removing devices.")
            return
        
        if self.num_devices <= 2:
            messagebox.showinfo("Cannot Remove", "Must have at least 2 devices.")
            return
        
        # Remove the last device widget
        if self.device_widgets:
            widget_dict = self.device_widgets.pop()
            widget_dict['device_frame'].destroy()
            widget_dict['volume_frame'].destroy()
            self.num_devices -= 1
            
            # Update device count label
            self.device_count_label.config(text=f"{self.num_devices} devices")
            
            print(f"✓ Removed Device {widget_dict['device_num']}")
    
    def update_device_combos(self):
        """Update all device combo boxes with available audio devices."""
        try:
            import sounddevice as sd
            
            # Get all output devices
            devices = sd.query_devices()
            output_devices = []
            
            for i, device in enumerate(devices):
                if device['max_output_channels'] > 0:
                    device_name = device['name']
                    max_channels = device['max_output_channels']
                    
                    # Add clear visual indicators
                    prefix = ""
                    
                    # Mark incompatible devices with warning
                    if max_channels < 2:
                        prefix = "⚠ MONO - "
                    elif 'headset' in device_name.lower():
                        prefix = "⚠ PHONE MODE - "
                    elif device_name.strip() == '' or device_name.strip() == '()':
                        prefix = "⚠ INVALID - "
                    # Mark good devices with checkmark
                    elif any(keyword in device_name.lower() for keyword in ['speakers', 'realtek', 'thx']):
                        prefix = "✓ "
                    elif 'bose' in device_name.lower():
                        prefix = "✓ "
                    
                    output_devices.append(f"{prefix}{device_name} (index: {i})")
            
            # Add "None" option at the beginning
            device_list = ["None"] + output_devices
            
            # Update Device 1 and Device 2 combos
            if hasattr(self, 'device1_combo'):
                self.device1_combo['values'] = device_list
                if self.device1_combo.current() == -1:
                    self.device1_combo.current(0)
            
            if hasattr(self, 'device2_combo'):
                self.device2_combo['values'] = device_list
                if self.device2_combo.current() == -1:
                    self.device2_combo.current(0)
            
            # Update all dynamically added device combos
            for widget_dict in self.device_widgets:
                combo = widget_dict['combo']
                combo['values'] = device_list
                if combo.current() == -1:
                    combo.current(0)
            
            print(f"✓ Updated device combos with {len(output_devices)} devices (✓ = compatible, ⚠ = incompatible)")
            
        except Exception as e:
            print(f"⚠ Error updating device combos: {e}")
            import traceback
            traceback.print_exc()
    
    def get_device_index_from_selection(self, selection_text):
        """Extract device index from dropdown selection text.
        
        Format: "Device Name (index: 42)" -> 42
        Returns None if selection is "None" or invalid.
        """
        if not selection_text or selection_text == "None":
            return None
        
        try:
            # Extract index from "(index: X)" format
            import re
            match = re.search(r'\(index:\s*(\d+)\)', selection_text)
            if match:
                return int(match.group(1))
            return None
        except Exception as e:
            print(f"⚠ Error extracting device index from '{selection_text}': {e}")
            return None
    
    def get_all_selected_devices(self):
        """Get all selected devices (Device 1, Device 2, and all dynamic devices).
        
        Returns list of tuples: [(device_num, device_index, device_name), ...]
        """
        devices = []
        
        # Get Device 1
        if hasattr(self, 'device1_combo'):
            selection = self.device1_combo.get()
            device_idx = self.get_device_index_from_selection(selection)
            if device_idx is not None:
                # Extract device name (everything before " (index:")
                device_name = selection.split(" (index:")[0] if " (index:" in selection else selection
                devices.append((1, device_idx, device_name))
        
        # Get Device 2
        if hasattr(self, 'device2_combo'):
            selection = self.device2_combo.get()
            device_idx = self.get_device_index_from_selection(selection)
            if device_idx is not None:
                device_name = selection.split(" (index:")[0] if " (index:" in selection else selection
                devices.append((2, device_idx, device_name))
        
        # Get all dynamically added devices
        for widget_dict in self.device_widgets:
            device_num = widget_dict['device_num']
            combo = widget_dict['combo']
            selection = combo.get()
            device_idx = self.get_device_index_from_selection(selection)
            if device_idx is not None:
                device_name = selection.split(" (index:")[0] if " (index:" in selection else selection
                devices.append((device_num, device_idx, device_name))
        
        return devices
    
    def update_playlist_display(self):
        """Update the playlist listbox display."""
        self.playlist_listbox.delete(0, tk.END)
        for i, item in enumerate(self.playlist):
            if item['type'] == 'local':
                display = f"{i+1}. {os.path.basename(item['path'])}"
            else:
                display = f"{i+1}. {item.get('artist', 'Unknown')} - {item.get('title', 'Unknown')}"
            self.playlist_listbox.insert(tk.END, display)
        
        # Update status
        if len(self.playlist) == 0:
            self.playlist_status_label.config(text="Playlist is empty", fg="gray")
        else:
            self.playlist_status_label.config(text=f"Playlist: {len(self.playlist)} songs", fg="green")
    
    def add_local_to_playlist(self):
        """Add a local file to the playlist."""
        file_path = filedialog.askopenfilename(
            title="Add Audio File to Playlist",
            filetypes=[
                ("Audio files", "*.mp3 *.wav *.ogg *.flac *.m4a"),
                ("MP3 files", "*.mp3"),
                ("WAV files", "*.wav"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            # Validate the selected file
            is_valid, error_msg = validate_audio_file(file_path)
            if not is_valid:
                messagebox.showerror("Invalid Audio File", error_msg)
                return
            
            self.playlist.append({
                'type': 'local',
                'path': file_path,
                'title': os.path.basename(file_path),
                'artist': 'Local File'
            })
            self.update_playlist_display()
    
    def add_soundcloud_to_playlist(self):
        """Add selected SoundCloud track to playlist."""
        if not self.streaming_manager:
            messagebox.showwarning("Streaming Unavailable", "SoundCloud streaming is not available.")
            return
        
        # Check if we have search results
        if not hasattr(self, 'search_results') or not self.search_results:
            messagebox.showinfo("No Selection", "Please search and select a track from SoundCloud first.")
            return
        
        # Get selection from SoundCloud results
        # We'll use a simple dialog to select from recent search results
        # For now, add the first result if available, or prompt user
        if len(self.search_results) > 0:
            # Add all search results or let user select
            # For simplicity, we'll add the currently selected one if listbox exists
            if hasattr(self, 'results_listbox'):
                selection = self.results_listbox.curselection()
                if selection:
                    track = self.search_results[selection[0]]
                    self.playlist.append({
                        'type': 'streaming',
                        'path': track.get('url', ''),
                        'title': track.get('title', 'Unknown'),
                        'artist': track.get('artist', 'Unknown'),
                        'track_info': track
                    })
                    self.update_playlist_display()
                else:
                    messagebox.showinfo("No Selection", "Please select a track from the SoundCloud search results.")
            else:
                # Add first result
                track = self.search_results[0]
                self.playlist.append({
                    'type': 'streaming',
                    'path': track.get('url', ''),
                    'title': track.get('title', 'Unknown'),
                    'artist': track.get('artist', 'Unknown'),
                    'track_info': track
                })
                self.update_playlist_display()
    
    def remove_from_playlist(self):
        """Remove selected item from playlist."""
        selection = self.playlist_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.playlist):
                self.playlist.pop(index)
                # Adjust current index if needed
                if self.current_playlist_index >= index:
                    self.current_playlist_index -= 1
                self.update_playlist_display()
    
    def clear_playlist(self):
        """Clear the entire playlist."""
        if len(self.playlist) > 0:
            if messagebox.askyesno("Clear Playlist", "Are you sure you want to clear the entire playlist?"):
                self.playlist = []
                self.current_playlist_index = -1
                self.update_playlist_display()
    
    def move_playlist_item_up(self):
        """Move selected playlist item up."""
        selection = self.playlist_listbox.curselection()
        if selection:
            index = selection[0]
            if index > 0:
                self.playlist[index], self.playlist[index-1] = self.playlist[index-1], self.playlist[index]
                if self.current_playlist_index == index:
                    self.current_playlist_index = index - 1
                elif self.current_playlist_index == index - 1:
                    self.current_playlist_index = index
                self.update_playlist_display()
                self.playlist_listbox.selection_set(index - 1)
    
    def move_playlist_item_down(self):
        """Move selected playlist item down."""
        selection = self.playlist_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.playlist) - 1:
                self.playlist[index], self.playlist[index+1] = self.playlist[index+1], self.playlist[index]
                if self.current_playlist_index == index:
                    self.current_playlist_index = index + 1
                elif self.current_playlist_index == index + 1:
                    self.current_playlist_index = index
                self.update_playlist_display()
                self.playlist_listbox.selection_set(index + 1)
    
    def play_playlist_item(self):
        """Play the selected playlist item."""
        selection = self.playlist_listbox.curselection()
        if selection:
            self.current_playlist_index = selection[0]
            self.play_current_playlist_item()
    
    def play_current_playlist_item(self):
        """Play the current playlist item."""
        if self.current_playlist_index < 0 or self.current_playlist_index >= len(self.playlist):
            print(f"Invalid playlist index: {self.current_playlist_index} (playlist length: {len(self.playlist)})")
            return
        
        if not self.playlist_playing:
            print("Playlist is not playing, cannot start track")
            return
        
        item = self.playlist[self.current_playlist_index]
        print(f"Playing playlist item {self.current_playlist_index + 1}/{len(self.playlist)}: {item.get('title', 'Unknown')}")
        
        def play_thread():
            try:
                # Get audio file path
                if item['type'] == 'local':
                    audio_file = item['path']
                    if not os.path.exists(audio_file):
                        try:
                            self.root.after(0, lambda: messagebox.showerror("Error", f"File not found: {audio_file}"))
                        except:
                            pass
                        return
                else:
                    # Download from SoundCloud
                    try:
                        self.root.after(0, lambda: self.status_label.config(
                            text=f"Downloading {item['title']}...", fg="blue"
                        ))
                    except:
                        pass
                    
                    if not hasattr(self, 'streaming_manager') or not self.streaming_manager:
                        error_msg = "Streaming manager not available"
                        print(error_msg)
                        try:
                            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
                        except:
                            pass
                        return
                    
                    try:
                        audio_file = self.streaming_manager.get_audio_file(item.get('track_info', item))
                    except Exception as e:
                        print(f"Error downloading track: {e}")
                        import traceback
                        traceback.print_exc()
                        try:
                            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to download track: {e}"))
                        except:
                            pass
                        return
                    
                    if not audio_file or not os.path.exists(audio_file):
                        try:
                            self.root.after(0, lambda: messagebox.showerror("Error", "Failed to download track"))
                        except:
                            pass
                        return
                
                # Play the file
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Playing: {item['title']}", fg="green"
                ))
                self.root.after(0, lambda: self.playlist_status_label.config(
                    text=f"Now playing: {item['title']}", fg="blue"
                ))
                
                # Stop any existing player first
                try:
                    if self.player:
                        print("Stopping existing player before starting next track...")
                        self.player.stop()
                        time.sleep(0.3)  # Longer pause to ensure cleanup
                        print("Existing player stopped")
                except Exception as e:
                    print(f"Error stopping existing player: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue anyway - try to start new player
                
                # Create new player
                try:
                    print("Creating new player instance...")
                    self.player = SynchronizedAudioPlayer(
                        device1=self.device1_index,
                        device2=self.device2_index,
                        device1_latency_adjustment=self.device1_latency_adjustment / 1000.0,  # Convert ms to seconds
                        device2_latency_adjustment=self.device2_latency_adjustment / 1000.0   # Convert ms to seconds
                    )
                    # Set volumes
                    self.player.set_volume(1, self.volume1_var.get() / 100.0)
                    self.player.set_volume(2, self.volume2_var.get() / 100.0)
                    print(f"Loading audio file: {os.path.basename(audio_file)}")
                    self.player.load_audio_file(audio_file)
                except Exception as e:
                    print(f"Error creating/loading player: {e}")
                    import traceback
                    traceback.print_exc()
                    raise  # Re-raise to be caught by outer exception handler
                
                # Start playback (this will block until playback completes)
                # We're already in a thread (play_thread), so this won't block the GUI
                try:
                    print(f"Starting playback of: {item.get('title', 'Unknown')}")
                    self.player.play()
                    print(f"Playback completed for: {item.get('title', 'Unknown')}")
                except Exception as e:
                    print(f"Error during playback: {e}")
                    import traceback
                    traceback.print_exc()
                    raise  # Re-raise to be caught by outer exception handler
                
                # After playback completes, auto-advance if still playing
                # Check playlist_playing flag again after a brief delay to ensure it's still valid
                time.sleep(0.1)  # Brief check delay
                
                # Check if player is paused - if so, don't auto-advance
                player_paused = False
                if self.player and hasattr(self.player, 'is_paused'):
                    player_paused = self.player.is_paused
                
                # Debug: Log current state
                print(f"Playback finished. State check: playlist_playing={self.playlist_playing}, playlist_advancing={self.playlist_advancing}, player_paused={player_paused}, index={self.current_playlist_index}/{len(self.playlist)}")
                
                # Only auto-advance if playing, not advancing, and NOT paused
                if self.playlist_playing and not self.playlist_advancing and not player_paused:
                    # Small delay to ensure playback is fully complete
                    time.sleep(0.2)
                    # Check one more time before auto-advancing (including pause check)
                    player_paused = False
                    if self.player and hasattr(self.player, 'is_paused'):
                        player_paused = self.player.is_paused
                    
                    if self.playlist_playing and not self.playlist_advancing and not player_paused:
                        # Auto-advance to next track
                        print("Auto-advancing to next track...")
                        try:
                            # Use after_idle to ensure it runs on the main thread
                            self.root.after_idle(self.next_playlist_item)
                        except Exception as e:
                            print(f"Error scheduling auto-advance: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        if player_paused:
                            print("Playback is paused, not auto-advancing")
                        else:
                            print(f"Playback ended, not auto-advancing (playlist_playing={self.playlist_playing}, advancing={self.playlist_advancing})")
                        # Update UI safely
                        try:
                            self.root.after_idle(lambda: self._safe_update_status("Playback completed", "gray"))
                            self.root.after_idle(lambda: self._safe_update_playlist_status(f"Playlist: {len(self.playlist)} songs", "green"))
                        except Exception as e:
                            print(f"Error updating UI after playback: {e}")
                else:
                    # Playback was stopped or playlist ended or paused
                    print(f"Playback ended, not auto-advancing (playlist_playing={self.playlist_playing}, advancing={self.playlist_advancing}, paused={player_paused})")
                    # Update UI safely
                    try:
                        self.root.after_idle(lambda: self._safe_update_status("Playback completed", "gray"))
                        self.root.after_idle(lambda: self._safe_update_playlist_status(f"Playlist: {len(self.playlist)} songs", "green"))
                    except Exception as e:
                        print(f"Error updating UI after playback: {e}")
                
            except Exception as e:
                print(f"Error in playlist playback thread: {e}")
                import traceback
                traceback.print_exc()
                # Update UI safely
                try:
                    self.root.after(0, lambda: messagebox.showerror("Playback Error", str(e)))
                    self.root.after(0, lambda: self.status_label.config(text="Error occurred", fg="red"))
                except Exception as ui_error:
                    print(f"Error updating UI: {ui_error}")
                # If error occurred, stop playlist
                self.playlist_playing = False
                self.playlist_advancing = False
        
        # Wrap play_thread in an outer exception handler to catch any unhandled exceptions
        def safe_play_thread():
            """Wrapper to ensure thread never crashes the app."""
            try:
                play_thread()
            except Exception as e:
                print(f"CRITICAL: Unhandled exception in play_thread: {e}")
                import traceback
                traceback.print_exc()
                # Try to update UI
                try:
                    self.root.after(0, lambda: self.status_label.config(text="Critical playback error", fg="red"))
                except:
                    pass
                # Reset state
                self.playlist_playing = False
                self.playlist_advancing = False
        
        # Start thread with comprehensive error handling
        try:
            thread = threading.Thread(target=safe_play_thread, daemon=True)
            thread.start()
        except Exception as e:
            print(f"Error starting playback thread: {e}")
            import traceback
            traceback.print_exc()
            self.playlist_playing = False
            self.playlist_advancing = False
            try:
                self.status_label.config(text="Error starting playback", fg="red")
            except:
                pass
    
    def play_playlist(self):
        """Start playing the playlist from the beginning."""
        if len(self.playlist) == 0:
            messagebox.showinfo("Empty Playlist", "The playlist is empty. Add some songs first.")
            return
        
        self.playlist_playing = True
        self.current_playlist_index = 0
        self.play_playlist_btn.config(state=tk.DISABLED)
        self.pause_playlist_btn.config(text="Pause", state=tk.NORMAL)
        self.stop_playlist_btn.config(state=tk.NORMAL)
        self.play_current_playlist_item()
    
    def pause_playlist(self):
        """Pause/resume playlist playback."""
        try:
            # Validate player exists and is valid
            if not self.player:
                print("No player available for pause/resume")
                return
            
            # Validate playlist exists
            if not hasattr(self, 'playlist') or not self.playlist:
                print("Playlist not available")
                return
            
            # Validate playlist index (allow -1 for stopped state)
            if self.current_playlist_index < -1 or (self.current_playlist_index >= 0 and self.current_playlist_index >= len(self.playlist)):
                print(f"Invalid playlist index: {self.current_playlist_index}")
                return
            
            # Check if player has is_paused attribute
            if not hasattr(self.player, 'is_paused'):
                print("Player does not have is_paused attribute")
                return
            
            # Check if player is playing (allow pause even if transitioning)
            if not hasattr(self.player, 'is_playing'):
                print("Player does not have is_playing attribute")
                return
            
            # Only allow pause/resume if player is actually playing or paused
            if not self.player.is_playing and not self.player.is_paused:
                print("Player is not playing and not paused, cannot pause/resume")
                return
            
            try:
                if self.player.is_paused:
                    # Resume playback
                    try:
                        self.player.resume()
                        print("Playlist resumed")
                    except Exception as e:
                        print(f"Error resuming player: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't return - try to update UI anyway
                    
                    # Update UI safely - always try even if resume had error
                    try:
                        if hasattr(self, 'pause_playlist_btn') and self.pause_playlist_btn:
                            self.pause_playlist_btn.config(text="Pause")
                        if hasattr(self, 'playlist') and self.current_playlist_index >= 0 and self.current_playlist_index < len(self.playlist):
                            song_title = self.playlist[self.current_playlist_index].get('title', 'Unknown')
                            if hasattr(self, 'playlist_status_label') and self.playlist_status_label:
                                self.playlist_status_label.config(text=f"Now playing: {song_title}", fg="blue")
                        self._safe_update_status("Resumed", "green")
                    except Exception as e:
                        print(f"Error updating UI after resume: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    # Pause playback
                    try:
                        self.player.pause()
                        print("Playlist paused")
                    except Exception as e:
                        print(f"Error pausing player: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't return - try to update UI anyway
                    
                    # Update UI safely - always try even if pause had error
                    try:
                        if hasattr(self, 'pause_playlist_btn') and self.pause_playlist_btn:
                            self.pause_playlist_btn.config(text="Resume")
                        if hasattr(self, 'playlist') and self.current_playlist_index >= 0 and self.current_playlist_index < len(self.playlist):
                            song_title = self.playlist[self.current_playlist_index].get('title', 'Unknown')
                            if hasattr(self, 'playlist_status_label') and self.playlist_status_label:
                                self.playlist_status_label.config(text=f"Paused: {song_title}", fg="orange")
                        self._safe_update_status("Paused", "orange")
                    except Exception as e:
                        print(f"Error updating UI after pause: {e}")
                        import traceback
                        traceback.print_exc()
            except AttributeError as e:
                print(f"Player attribute error: {e}")
                import traceback
                traceback.print_exc()
                # Don't crash - just log the error
            except Exception as e:
                print(f"Unexpected error in pause/resume logic: {e}")
                import traceback
                traceback.print_exc()
                # Don't crash - just log the error
        except Exception as e:
            print(f"Critical error in pause_playlist: {e}")
            import traceback
            traceback.print_exc()
            # Try to update UI to show error - but don't crash if this fails
            try:
                self._safe_update_status("Error pausing/resuming", "red")
            except:
                pass
            # Never re-raise - always prevent crash
    
    def stop_playlist(self):
        """Stop playlist playback."""
        try:
            # Set flags first to prevent race conditions
            self.playlist_playing = False
            self.playlist_advancing = False  # Reset advancing flag
            
            # Stop player if it exists
            if self.player:
                try:
                    self.player.stop()
                except Exception as e:
                    print(f"Error calling player.stop(): {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue - don't let stop errors crash the app
                
                # Give time for cleanup, but don't crash if sleep fails
                try:
                    time.sleep(0.2)  # Give time for cleanup
                except Exception as e:
                    print(f"Error in sleep: {e}")
                    # Continue anyway
        except Exception as e:
            print(f"Error stopping playlist: {e}")
            import traceback
            traceback.print_exc()
            # Don't re-raise - always continue to UI update
        finally:
            # Always update UI, even if stop() had an error
            try:
                self.current_playlist_index = -1
                if hasattr(self, 'play_playlist_btn') and self.play_playlist_btn:
                    self.play_playlist_btn.config(state=tk.NORMAL)
                if hasattr(self, 'pause_playlist_btn') and self.pause_playlist_btn:
                    self.pause_playlist_btn.config(text="Pause", state=tk.DISABLED)
                if hasattr(self, 'stop_playlist_btn') and self.stop_playlist_btn:
                    self.stop_playlist_btn.config(state=tk.DISABLED)
                self._safe_update_status("Playlist stopped", "gray")
                if hasattr(self, 'playlist_status_label') and self.playlist_status_label:
                    playlist_count = len(self.playlist) if hasattr(self, 'playlist') else 0
                    self.playlist_status_label.config(text=f"Playlist: {playlist_count} songs", fg="green")
            except Exception as e:
                print(f"Error updating UI after stop_playlist: {e}")
                import traceback
                traceback.print_exc()
                # Never re-raise - prevent crash
    
    def next_playlist_item(self):
        """Play the next item in the playlist."""
        # Prevent race conditions - only allow one advance at a time
        if self.playlist_advancing:
            print("Playlist already advancing, skipping duplicate call")
            return
        
        if not self.playlist_playing:
            print("Playlist is not playing, cannot advance")
            return
        
        self.playlist_advancing = True
        
        try:
            print("Stopping current track...")
            # Stop current playback first
            try:
                if self.player:
                    self.player.stop()
                    # Wait for player to fully stop
                    time.sleep(0.3)  # Delay for cleanup
            except Exception as e:
                print(f"Error stopping current track: {e}")
                import traceback
                traceback.print_exc()
                # Continue anyway - don't let stop errors prevent advancing
            
            # Validate playlist exists
            if not hasattr(self, 'playlist') or len(self.playlist) == 0:
                print("Playlist is empty or doesn't exist")
                self.playlist_playing = False
                self.playlist_advancing = False
                try:
                    self._safe_update_status("Playlist is empty", "red")
                except:
                    pass
                return
            
            # Increment index
            self.current_playlist_index += 1
            print(f"Advanced to index: {self.current_playlist_index}")
            
            if self.current_playlist_index >= len(self.playlist):
                # End of playlist
                print("Reached end of playlist")
                self.playlist_playing = False
                self.current_playlist_index = -1
                try:
                    if hasattr(self, 'play_playlist_btn') and self.play_playlist_btn:
                        self.play_playlist_btn.config(state=tk.NORMAL)
                    if hasattr(self, 'pause_playlist_btn') and self.pause_playlist_btn:
                        self.pause_playlist_btn.config(text="Pause", state=tk.DISABLED)
                    if hasattr(self, 'stop_playlist_btn') and self.stop_playlist_btn:
                        self.stop_playlist_btn.config(state=tk.DISABLED)
                    self._safe_update_status("Playlist completed", "gray")
                    if hasattr(self, 'playlist_status_label') and self.playlist_status_label:
                        playlist_count = len(self.playlist) if hasattr(self, 'playlist') else 0
                        self.playlist_status_label.config(text=f"Playlist: {playlist_count} songs", fg="green")
                except Exception as e:
                    print(f"Error updating UI: {e}")
                    import traceback
                    traceback.print_exc()
                self.playlist_advancing = False  # Reset flag before returning
                return
            
            # Reset flag BEFORE starting next track (so it can play)
            self.playlist_advancing = False
            
            # Play the next item
            print(f"Starting next track: {self.current_playlist_index + 1} of {len(self.playlist)}")
            try:
                # Call play_current_playlist_item in a safe way
                self.play_current_playlist_item()
            except Exception as e:
                print(f"Error in next_playlist_item when calling play_current_playlist_item: {e}")
                import traceback
                traceback.print_exc()
                self.playlist_playing = False
                try:
                    self._safe_update_status("Error starting next track", "red")
                except Exception as ui_error:
                    print(f"Error updating UI: {ui_error}")
            
        except Exception as e:
            print(f"Critical error in next_playlist_item: {e}")
            import traceback
            traceback.print_exc()
            # Don't let exceptions crash the app
            try:
                self.playlist_playing = False
                self._safe_update_status("Error advancing playlist", "red")
            except Exception as ui_error:
                print(f"Error updating UI after critical error: {ui_error}")
            finally:
                self.playlist_advancing = False  # Always reset flag
    
    def pause_audio(self):
        """Pause audio playback."""
        try:
            # Validate player exists
            if not self.player:
                print("No player available for pause/resume")
                return
            
            # Check if player has required attributes
            if not hasattr(self.player, 'is_paused'):
                print("Player does not have is_paused attribute")
                return
            
            # Check if player has is_playing attribute
            if not hasattr(self.player, 'is_playing'):
                print("Player does not have is_playing attribute")
                return
            
            # Only allow pause/resume if player is actually playing or paused
            if not self.player.is_playing and not self.player.is_paused:
                print("Player is not playing and not paused, cannot pause/resume")
                return
            
            try:
                if self.player.is_paused:
                    # Resume playback
                    try:
                        self.player.resume()
                        print("Audio resumed")
                    except Exception as e:
                        print(f"Error resuming player: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't return - try to update UI anyway
                    
                    # Update UI safely - always try even if resume had error
                    try:
                        if hasattr(self, 'pause_btn') and self.pause_btn:
                            self.pause_btn.config(text="Pause")
                        self._safe_update_status("Resumed", "green")
                    except Exception as e:
                        print(f"Error updating UI after resume: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    # Pause playback
                    try:
                        self.player.pause()
                        print("Audio paused")
                    except Exception as e:
                        print(f"Error pausing player: {e}")
                        import traceback
                        traceback.print_exc()
                        # Don't return - try to update UI anyway
                    
                    # Update UI safely - always try even if pause had error
                    try:
                        if hasattr(self, 'pause_btn') and self.pause_btn:
                            self.pause_btn.config(text="Resume")
                        self._safe_update_status("Paused", "orange")
                    except Exception as e:
                        print(f"Error updating UI after pause: {e}")
                        import traceback
                        traceback.print_exc()
            except AttributeError as e:
                print(f"Player attribute error: {e}")
                import traceback
                traceback.print_exc()
                # Don't crash - just log the error
            except Exception as e:
                print(f"Unexpected error in pause/resume logic: {e}")
                import traceback
                traceback.print_exc()
                # Don't crash - just log the error
        except Exception as e:
            print(f"Critical error in pause_audio: {e}")
            import traceback
            traceback.print_exc()
            # Try to update UI to show error - but don't crash if this fails
            try:
                self._safe_update_status("Error pausing/resuming", "red")
            except Exception as ui_error:
                print(f"Error updating status after critical error: {ui_error}")
            # Never re-raise - always prevent crash
    
    def stop_audio(self):
        """Stop audio playback."""
        try:
            # Stop player if it exists
            if self.player:
                try:
                    self.player.stop()
                except Exception as e:
                    print(f"Error calling player.stop(): {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue - don't let stop errors crash the app
                
                # Brief pause for cleanup, but don't crash if sleep fails
                try:
                    time.sleep(0.1)  # Brief pause for cleanup
                except Exception as e:
                    print(f"Error in sleep: {e}")
                    # Continue anyway
        except Exception as e:
            print(f"Error in stop_audio: {e}")
            import traceback
            traceback.print_exc()
            # Don't re-raise - always continue to UI update
        finally:
            # Always update UI, even if stop() had an error
            try:
                self._safe_update_status("Stopped", "gray")
                if hasattr(self, 'play_btn') and self.play_btn:
                    self.play_btn.config(state=tk.NORMAL)
                if hasattr(self, 'pause_btn') and self.pause_btn:
                    self.pause_btn.config(text="Pause", state=tk.DISABLED)
                if hasattr(self, 'stop_btn') and self.stop_btn:
                    self.stop_btn.config(state=tk.DISABLED)
            except Exception as e:
                print(f"Error updating UI after stop: {e}")
                import traceback
                traceback.print_exc()
                # Never re-raise - prevent crash
    
    def on_volume1_changed(self, value):
        """Handle volume 1 slider change."""
        vol = float(value) / 100.0
        self.volume1_label.config(text=f"{int(float(value))}%")
        # Update thread-safe cache
        with self._volume_cache_lock:
            self._volume_cache[1] = vol
        if self.player:
            self.player.set_volume(1, vol)
    
    def on_volume2_changed(self, value):
        """Handle volume 2 slider change."""
        vol = float(value) / 100.0
        self.volume2_label.config(text=f"{int(float(value))}%")
        # Update thread-safe cache
        with self._volume_cache_lock:
            self._volume_cache[2] = vol
        if self.player:
            self.player.set_volume(2, vol)
    
    def _safe_update_status(self, text, fg="black"):
        """Safely update status label."""
        try:
            if hasattr(self, 'status_label') and self.status_label:
                self.status_label.config(text=text, fg=fg)
        except Exception as e:
            print(f"Error updating status label: {e}")
    
    def _safe_update_playlist_status(self, text, fg="black"):
        """Safely update playlist status label."""
        try:
            if hasattr(self, 'playlist_status_label') and self.playlist_status_label:
                self.playlist_status_label.config(text=text, fg=fg)
        except Exception as e:
            print(f"Error updating playlist status label: {e}")
    
    def measure_device_latency(self, device_num, device_index, device_name):
        """Measure latency for a device in a background thread."""
        if device_index is None:
            return
        
        def measure_thread():
            try:
                self.status_label.config(text=f"Measuring latency for Device {device_num}...", fg="blue")
                # Create a temporary player instance to measure latency
                # Supports any device number by just passing it as device1
                temp_player = SynchronizedAudioPlayer(device1=device_index, device2=None)
                # Get sample rate from device info
                sample_rate = 44100
                try:
                    # Import sounddevice check function from player module
                    import sounddevice as sd
                    device_info = sd.query_devices(device_index)
                    sample_rate = int(device_info.get('default_samplerate', 44100))
                except:
                    pass
                
                # Measure latency
                measured_latency_ms = temp_player._get_device_latency(device_index, device_name, sample_rate, measure=True) * 1000.0
                
                # Update UI on main thread
                self.root.after(0, lambda: self._update_latency_measurement(device_num, measured_latency_ms))
            except Exception as e:
                print(f"Error measuring latency: {e}")
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.status_label.config(text="Latency measurement failed", fg="orange"))
        
        thread = threading.Thread(target=measure_thread, daemon=True)
        thread.start()
    
    def measure_all_devices(self):
        """Measure latency for all selected devices (Device 1, 2, and dynamic devices) in sequence.
        Stored values are used at passthrough start for faster sync with many speakers."""
        try:
            all_selected = self.get_all_selected_devices()
            if not all_selected:
                self.status_label.config(text="Select at least one device first", fg="orange")
                return
        except Exception as e:
            print(f"Error getting selected devices: {e}")
            self.status_label.config(text="Could not get device list", fg="orange")
            return
        
        def measure_all_thread():
            try:
                for i, (device_num, device_idx, device_name) in enumerate(all_selected):
                    self.root.after(0, lambda n=device_num, i=i, total=len(all_selected):
                        self.status_label.config(text=f"Measuring Device {n}... ({i+1}/{total})", fg="blue"))
                    sample_rate = 44100
                    try:
                        import sounddevice as sd
                        device_info = sd.query_devices(device_idx)
                        sample_rate = int(device_info.get('default_samplerate', 44100))
                    except Exception:
                        pass
                    measured_latency_ms = None
                    try:
                        if hasattr(self, 'player') and self.player is not None:
                            lat = self.player._get_device_latency(device_idx, device_name, sample_rate, measure=True)
                            if lat and lat > 0:
                                measured_latency_ms = lat * 1000.0
                        if measured_latency_ms is None:
                            temp_player = SynchronizedAudioPlayer(device1=device_idx, device2=None)
                            measured_latency_ms = temp_player._get_device_latency(
                                device_idx, device_name, sample_rate, measure=True) * 1000.0
                    except Exception as e:
                        print(f"Error measuring Device {device_num}: {e}")
                        measured_latency_ms = 0.0
                    if measured_latency_ms is not None and measured_latency_ms > 0:
                        self.root.after(0, lambda n=device_num, ms=measured_latency_ms:
                            self._update_latency_measurement(n, ms))
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Measured {len(all_selected)} device(s) - ready for sync", fg="green"))
            except Exception as e:
                print(f"Error in measure_all_devices: {e}")
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.status_label.config(text="Measure all failed", fg="orange"))
        
        threading.Thread(target=measure_all_thread, daemon=True).start()
    
    def _update_latency_measurement(self, device_num, measured_latency_ms):
        """Update latency measurement display."""
        try:
            if device_num == 1:
                self.device1_measured_latency = measured_latency_ms
                self.device1_latency_label.config(text=f"(auto: {measured_latency_ms:.0f}ms)", fg="green")
                self.device1_latency_label_sc.config(text=f"(auto: {measured_latency_ms:.0f}ms)", fg="green")
                # Auto-set the adjustment to 0 (no adjustment, use measured value)
                # User can then adjust relative to this measured value
                self.device1_latency_var.set(0.0)
                self.device1_latency_adjustment = 0.0
            elif device_num == 2:
                self.device2_measured_latency = measured_latency_ms
                self.device2_latency_label.config(text=f"(auto: {measured_latency_ms:.0f}ms)", fg="green")
                self.device2_latency_label_sc.config(text=f"(auto: {measured_latency_ms:.0f}ms)", fg="green")
                # Auto-set the adjustment to 0 (no adjustment, use measured value)
                # User can then adjust relative to this measured value
                self.device2_latency_var.set(0.0)
                self.device2_latency_adjustment = 0.0
            else:
                # Dynamic device (3+)
                for w in self.device_widgets:
                    if w['device_num'] == device_num:
                        # Update stored value
                        w['measured_latency'] = measured_latency_ms
                        # Update label
                        w['latency_label'].config(text=f"(auto: {measured_latency_ms:.0f}ms)", fg="green")
                        # Reset manual adjustment
                        w['latency_var'].set(0.0)
                        break
            
            self.status_label.config(text=f"Device {device_num} latency: {measured_latency_ms:.0f}ms", fg="green")
        except Exception as e:
            print(f"Error updating latency measurement: {e}")
    
    def on_device1_latency_changed(self):
        """Handle device 1 latency adjustment change."""
        try:
            adjustment = float(self.device1_latency_var.get())
            self.device1_latency_adjustment = adjustment
            # Update label to show manual adjustment
            if abs(adjustment - self.device1_measured_latency) > 1.0:
                self.device1_latency_label.config(text=f"(manual: {adjustment:.0f}ms)", fg="blue")
                self.device1_latency_label_sc.config(text=f"(manual: {adjustment:.0f}ms)", fg="blue")
            else:
                self.device1_latency_label.config(text=f"(auto: {self.device1_measured_latency:.0f}ms)", fg="green")
                self.device1_latency_label_sc.config(text=f"(auto: {self.device1_measured_latency:.0f}ms)", fg="green")
            print(f"Device 1 latency adjustment set to: {adjustment:.1f}ms")
        except Exception as e:
            print(f"Error setting device 1 latency: {e}")
    
    def on_device2_latency_changed(self):
        """Handle device 2 latency adjustment change."""
        try:
            adjustment = float(self.device2_latency_var.get())
            self.device2_latency_adjustment = adjustment
            # Update label to show manual adjustment
            if abs(adjustment - self.device2_measured_latency) > 1.0:
                self.device2_latency_label.config(text=f"(manual: {adjustment:.0f}ms)", fg="blue")
                self.device2_latency_label_sc.config(text=f"(manual: {adjustment:.0f}ms)", fg="blue")
            else:
                self.device2_latency_label.config(text=f"(auto: {self.device2_measured_latency:.0f}ms)", fg="green")
                self.device2_latency_label_sc.config(text=f"(auto: {self.device2_measured_latency:.0f}ms)", fg="green")
            print(f"Device 2 latency adjustment set to: {adjustment:.1f}ms")
        except Exception as e:
            print(f"Error setting device 2 latency: {e}")
    
    def on_distributed_mode_changed(self):
        """Handle distributed mode change."""
        mode = self.distributed_mode.get()
        
        if not DISTRIBUTED_AVAILABLE:
            return
        
        if mode == "fleet":
            # Show network configuration
            self.distributed_network_frame.pack(fill=tk.X, pady=5)
            self.fleet_status_label.config(
                text="Fleet Mode: Configure master IP and ports, then start passthrough",
                fg=self.colors['accent_primary']
            )
        elif mode == "master":
            # Hide network configuration
            self.distributed_network_frame.pack_forget()
            self.fleet_status_label.config(
                text="Master Mode: Will distribute audio to fleet nodes when started",
                fg=self.colors['accent_success']
            )
        else:  # local
            # Hide network configuration
            self.distributed_network_frame.pack_forget()
            self.fleet_status_label.config(
                text="Mode: Local - No distributed features active",
                fg=self.colors['text_secondary']
            )
            
            # Stop any active distributed components
            if self.master_node:
                try:
                    self.master_node.stop()
                except:
                    pass
                self.master_node = None
            
            if self.fleet_node:
                try:
                    self.fleet_node.disconnect()
                except:
                    pass
                self.fleet_node = None
    
    def _start_fleet_status_updates(self):
        """Start thread to update fleet status display."""
        if not DISTRIBUTED_AVAILABLE:
            return
        
        def update_thread():
            while self.passthrough_active:
                try:
                    time.sleep(2.0)  # Update every 2 seconds
                    
                    if self.master_node:
                        status = self.master_node.get_fleet_status()
                        status_text = f"Master Mode: {status['node_count']} node(s) connected | Fleet ID: {status['fleet_id']}"
                        if status['node_count'] > 0:
                            status_text += f" | Chunks sent: {status['chunk_sequence']}"
                        self.root.after(0, lambda: self.fleet_status_label.config(
                            text=status_text,
                            fg=self.colors['accent_success']
                        ))
                    elif self.fleet_node and self.fleet_node.connected:
                        status = self.fleet_node.get_status()
                        status_text = f"Fleet Mode: Connected | Jitter: {status['jitter_ms']:.1f}ms | Clock offset: {status['clock_offset_ms']:.1f}ms | Buffer: {status['buffer_fill_ms']:.0f}ms"
                        self.root.after(0, lambda: self.fleet_status_label.config(
                            text=status_text,
                            fg=self.colors['accent_success']
                        ))
                except Exception as e:
                    print(f"Error updating fleet status: {e}")
        
        self.fleet_status_update_thread = threading.Thread(target=update_thread, daemon=True)
        self.fleet_status_update_thread.start()
    
    def start_audio_passthrough(self):
        """Start capturing system audio and routing to selected devices."""
        if self.passthrough_active:
            messagebox.showwarning("Already Active", "Audio pass-through is already running.")
            return
        
        if self.device1_index is None and self.device2_index is None:
            messagebox.showwarning(
                "No Devices Selected",
                "Please select at least one output device before starting pass-through."
            )
            return
        
        # Ensure previous passthrough is fully stopped before starting new one
        if hasattr(self, 'passthrough_thread') and self.passthrough_thread and self.passthrough_thread.is_alive():
            print("⚠ Previous passthrough thread still running - waiting for it to stop...")
            self.passthrough_active = False
            self.passthrough_thread.join(timeout=3.0)
            if self.passthrough_thread.is_alive():
                print("⚠⚠⚠ Warning: Previous passthrough thread did not stop - forcing cleanup")
            # Clear any leftover streams
            if hasattr(self, 'passthrough_streams'):
                try:
                    for stream in self.passthrough_streams:
                        try:
                            if hasattr(stream, 'stop'):
                                stream.stop()
                            if hasattr(stream, 'close'):
                                stream.close()
                        except:
                            pass
                except:
                    pass
                self.passthrough_streams = []
        
        self.passthrough_active = True
        self.start_passthrough_btn.config(state=tk.DISABLED)
        self.stop_passthrough_btn.config(state=tk.NORMAL)
        
        # Check if ready mode is enabled
        ready_mode = self.passthrough_ready_mode.get()
        if ready_mode:
            self.passthrough_status_label.config(text="Starting in Ready Mode - Waiting for audio...", fg="blue")
        else:
            self.passthrough_status_label.config(text="Starting audio pass-through...", fg="blue")
        
        def passthrough_thread():
            # Outer restart loop: keep passthrough running even if capture fails
            while self.passthrough_active:
                try:
                    import sounddevice as sd
                    import numpy as np
                    from collections import deque
                    import time
                    
                    # Round 9: Initialize distributed computing components
                    distributed_mode = self.distributed_mode.get() if DISTRIBUTED_AVAILABLE else "local"
                    
                    if distributed_mode == "master" and DISTRIBUTED_AVAILABLE:
                        # Initialize MasterNode
                        try:
                            self.master_node = MasterNode(
                                udp_port=self.master_udp_port.get(),
                                tcp_port=self.master_tcp_port.get()
                            )
                            self.master_node.start()
                            print(f"✓ Master Node started: {self.master_node.node_id}")
                            self.root.after(0, lambda: self.fleet_status_label.config(
                                text=f"Master Mode: Fleet ID {self.master_node.fleet_id} - Waiting for nodes...",
                                fg=self.colors['accent_success']
                            ))
                            # Start fleet status update thread
                            self._start_fleet_status_updates()
                        except Exception as e:
                            print(f"Error starting Master Node: {e}")
                            import traceback
                            traceback.print_exc()
                            self.root.after(0, lambda: self.fleet_status_label.config(
                                text=f"Master Mode Error: {str(e)}",
                                fg=self.colors['accent_danger']
                            ))
                    
                    elif distributed_mode == "fleet" and DISTRIBUTED_AVAILABLE:
                        # Initialize FleetNode
                        try:
                            self.fleet_node = FleetNode(
                                master_host=self.master_host.get(),
                                master_udp_port=self.master_udp_port.get(),
                                master_tcp_port=self.master_tcp_port.get(),
                                sample_rate=44100  # Will be updated when we know actual sample rate
                            )
                            if self.fleet_node.connect():
                                print(f"✓ Fleet Node connected: {self.fleet_node.node_id}")
                                self.root.after(0, lambda: self.fleet_status_label.config(
                                    text=f"Fleet Mode: Connected to {self.master_host.get()}",
                                    fg=self.colors['accent_success']
                                ))
                                # Start fleet status update thread
                                self._start_fleet_status_updates()
                            else:
                                print("✗ Failed to connect to master")
                                self.root.after(0, lambda: self.fleet_status_label.config(
                                    text="Fleet Mode: Connection failed - check master IP and ports",
                                    fg=self.colors['accent_danger']
                                ))
                        except Exception as e:
                            print(f"Error connecting Fleet Node: {e}")
                            import traceback
                            traceback.print_exc()
                            self.root.after(0, lambda: self.fleet_status_label.config(
                                text=f"Fleet Mode Error: {str(e)}",
                                fg=self.colors['accent_danger']
                            ))
                    
                    # Import volume control for muting original audio
                    try:
                        from audio_volume_control import mute_default_output, unmute_default_output, get_default_output_mute_state
                        volume_control_available = True
                    except ImportError:
                        volume_control_available = False
                        print("⚠ Volume control not available - original audio will not be muted")
                        print("  Install pycaw for automatic muting: pip install pycaw")
                    
                    # Store original mute state - will be set after we identify the capture device
                    original_mute_state = None
                    device_to_mute_name = None
                    
                    # Constants for audio processing
                    SILENCE_THRESHOLD = 0.01  # Consider silent if max level < 0.01
                    MAX_SILENT_CHUNKS = 15  # Stop buffering after N consecutive silent chunks (increased for music with pauses)
                    MIN_SILENT_BUFFER_CHUNKS = 3  # Keep N chunks when silent for quick resume
                    CALLBACK_FRAMES = 1024  # Standard callback size
                    VIRTUAL_CABLE_AUDIO_CHECK_WAIT = 5.0  # Seconds to wait before checking if virtual cable has audio
                    # REMOVED: CAPTURE_TIMEOUT - Don't exit on silence, only exit if actually stuck
                    # The watchdog (CAPTURE_STUCK_TIMEOUT) handles stuck detection
                    MAX_CONSECUTIVE_FAILURES = 10  # Increased from 5 - allow more failures before restarting
                    SAMPLE_RATE_MEASUREMENT_THRESHOLD = 0.15  # 15% difference threshold for trusting wall-clock measurements
                    CAPTURE_VOLUME_BOOST = 2.0  # Default volume boost for captured audio
                    BUFFER_MAX_SECONDS = 10  # Maximum buffer size in seconds
                    MONITOR_CHECK_INTERVAL = 5  # Seconds between health checks
                    DEBUG_LOG_FIRST_N_CALLBACKS = 20  # Log first N callbacks in detail
                    DEBUG_LOG_EVERY_N_CALLBACKS = 100  # Log every Nth callback
                    DEBUG_LOG_EVERY_N_CALLBACKS_SPARSE = 200  # Sparse logging interval
                    
                    # Try to use PyAudioWPatch for WASAPI loopback (better support)
                    pyaudiowpatch_available = False
                    pyaudiowpatch = None
                    try:
                        import pyaudiowpatch as pyaudio
                        # Test if it actually works by creating a PyAudio instance
                        test_p = pyaudio.PyAudio()
                        test_p.terminate()
                        pyaudiowpatch_available = True
                        pyaudiowpatch = pyaudio
                        print("✓ PyAudioWPatch available - will use for WASAPI loopback")
                    except ImportError as e:
                        print(f"PyAudioWPatch not available (ImportError: {e})")
                        print("For better WASAPI loopback support, install: pip install PyAudioWPatch")
                    except Exception as e:
                        print(f"PyAudioWPatch import failed: {e}")
                        print("Falling back to sounddevice")
                    
                    # On Windows, use WASAPI to access loopback devices
                    # First, try to find WASAPI loopback devices
                    devices = sd.query_devices()
                    loopback_device = None
                    input_device_name = None
                    
                    # Method 1: Use WASAPI loopback mode (Windows)
                    # On Windows, WASAPI allows accessing output devices as loopback inputs
                    print("Searching for WASAPI loopback devices...")
                    try:
                        # Get WASAPI host API
                        wasapi_hostapi = None
                        for hostapi_idx, hostapi_info in enumerate(sd.query_hostapis()):
                            if 'wasapi' in hostapi_info.get('name', '').lower():
                                wasapi_hostapi = hostapi_idx
                                break
                        
                        if wasapi_hostapi is not None:
                            # Get default output device
                            default_output = sd.default.device[1]
                            if default_output is not None:
                                default_output_info = sd.query_devices(default_output)
                                default_output_name = default_output_info['name']
                                
                                # In WASAPI, we can access output devices as loopback inputs
                                # by using the device index with WASAPI host API
                                # Try to find the WASAPI version of the default output
                                for i, device in enumerate(devices):
                                    device_hostapi = device.get('hostapi', -1)
                                    if device_hostapi == wasapi_hostapi:
                                        # Check if this is the output device we want
                                        # WASAPI loopback devices for outputs are typically
                                        # accessed by using the output device index as input
                                        # But we need to check device names match
                                        device_name = device['name']
                                        if device['max_output_channels'] > 0:
                                            # This is an output device, check if it matches default
                                            if default_output_name.lower() in device_name.lower() or \
                                               device_name.lower() in default_output_name.lower():
                                                # Try using this device index as a loopback input
                                                # In WASAPI, output devices can be accessed as loopback
                                                try:
                                                    # Test if we can access it as input (loopback)
                                                    test_info = sd.query_devices(i, kind='input')
                                                    if test_info['max_input_channels'] > 0:
                                                        loopback_device = i
                                                        input_device_name = f"{device_name} (WASAPI Loopback)"
                                                        print(f"Found WASAPI loopback for: {device_name}")
                                                        break
                                                except:
                                                    # Device might not support loopback, try next
                                                    pass
                    except Exception as e:
                        print(f"WASAPI loopback search error: {e}")
                    
                    # Method 2: Look for Stereo Mix or Virtual Audio Cables (if enabled)
                    # Virtual Audio Cables (like VB-Audio Cable) can provide "raw" audio capture
                    # because they bypass the Windows volume mixer when used as a virtual device
                    if loopback_device is None:
                        print("Searching for loopback devices (Stereo Mix, Virtual Audio Cables, Internal AUX, etc.)...")
                        for i, device in enumerate(devices):
                            if device['max_input_channels'] > 0:
                                device_name = device['name'].lower()
                                # Check for various loopback device names
                                loopback_keywords = [
                                    'stereo mix', 'what u hear', 'internal aux', 
                                    'aux jack', 'loopback', 'wave out mix',
                                    'vb-audio', 'virtual cable', 'voicemeeter', 'virtual audio'
                                ]
                                # Also check if it's NOT a microphone
                                is_mic = 'microphone' in device_name or 'mic' in device_name
                                if not is_mic and any(keyword in device_name for keyword in loopback_keywords):
                                    loopback_device = i
                                    input_device_name = device['name']
                                    print(f"Found loopback device: {device['name']} (index: {i})")
                                    print(f"  Max input channels: {device['max_input_channels']}")
                                    # Check if it's a virtual audio cable (these provide "raw" audio)
                                    is_virtual_cable = any(vc_keyword in device_name for vc_keyword in ['vb-audio', 'virtual cable', 'voicemeeter'])
                                    if is_virtual_cable:
                                        print(f"  ✓ Virtual Audio Cable detected - this can capture raw audio (bypasses Windows volume mixer)")
                                        print(f"  ✓ To use: Set this device as your default output in Windows, then capture from it")
                                    break
                    
                    # Method 3: Try to use default output device's loopback (WASAPI)
                    if loopback_device is None:
                        print("Trying to use default output device loopback...")
                        try:
                            # Get default output device
                            default_output = sd.default.device[1]
                            if default_output is not None:
                                default_output_info = sd.query_devices(default_output)
                                default_output_name = default_output_info['name']
                                print(f"Default output: {default_output_name}")
                                
                                # Try to find a loopback version by searching all devices
                                for i, device in enumerate(devices):
                                    device_name = device['name']
                                    # Check if this device name contains the output device name
                                    # and has loopback in it, or check if it's a WASAPI loopback
                                    if device['max_input_channels'] > 0:
                                        # Check host API
                                        hostapi_idx = device.get('hostapi', -1)
                                        try:
                                            hostapi_info = sd.query_hostapis(hostapi_idx)
                                            hostapi_name = hostapi_info.get('name', '').lower()
                                            if 'wasapi' in hostapi_name:
                                                # This might be a loopback device
                                                # On WASAPI, loopback devices often have similar names
                                                if default_output_name.lower() in device_name.lower() or \
                                                   device_name.lower() in default_output_name.lower():
                                                    loopback_device = i
                                                    input_device_name = device_name
                                                    print(f"Found potential WASAPI loopback: {device_name}")
                                                    break
                                        except:
                                            pass
                                
                                # If still not found, list all available input devices for debugging
                                if loopback_device is None:
                                    print("\nAvailable input devices:")
                                    for i, device in enumerate(devices):
                                        if device['max_input_channels'] > 0:
                                            hostapi_idx = device.get('hostapi', -1)
                                            try:
                                                hostapi_info = sd.query_hostapis(hostapi_idx)
                                                hostapi_name = hostapi_info.get('name', '')
                                            except:
                                                hostapi_name = 'Unknown'
                                            print(f"  [{i}] {device['name']} ({hostapi_name})")
                        except Exception as e:
                            print(f"Error finding default output loopback: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # Final fallback: Try using default output as WASAPI loopback directly
                    if loopback_device is None:
                        try:
                            # On Windows with WASAPI, we can try to use the default output device
                            # as a loopback input by specifying it with WASAPI host API
                            default_output = sd.default.device[1]
                            if default_output is not None:
                                default_output_info = sd.query_devices(default_output)
                                default_output_name = default_output_info['name']
                                
                                # Try to use WASAPI with the output device index
                                # This is a workaround - we'll try to access it as loopback
                                print(f"Attempting to use default output as WASAPI loopback: {default_output_name}")
                                
                                # Set WASAPI as the host API temporarily
                                wasapi_hostapi = None
                                for hostapi_idx, hostapi_info in enumerate(sd.query_hostapis()):
                                    if 'wasapi' in hostapi_info.get('name', '').lower():
                                        wasapi_hostapi = hostapi_idx
                                        break
                                
                                if wasapi_hostapi is not None:
                                    # Try using the output device index with WASAPI
                                    # In sounddevice, WASAPI loopback is accessed by using
                                    # the output device index but we need to specify it correctly
                                    loopback_device = default_output
                                    input_device_name = f"{default_output_name} (WASAPI Loopback)"
                                    print(f"Using WASAPI loopback mode with output device: {default_output_name}")
                                else:
                                    raise Exception("WASAPI not available")
                            else:
                                raise Exception("No default output device found")
                        except Exception as e:
                            error_msg = (
                                "No loopback device found.\n\n"
                                "To capture system audio on Windows:\n\n"
                                "OPTION 1: Enable Stereo Mix (Easiest)\n"
                                "1. Right-click speaker icon → Sounds\n"
                                "2. Recording tab → Right-click empty area\n"
                                "3. Check 'Show Disabled Devices'\n"
                                "4. Enable 'Stereo Mix'\n"
                                "5. Set as default recording device\n\n"
                                "OPTION 2: Use Virtual Audio Cable\n"
                                "Install VB-Audio Cable or VoiceMeeter\n\n"
                                f"Error: {str(e)}"
                            )
                            raise Exception(error_msg)
                    
                    # Initialize sample rate and channels - will be updated by PyAudioWPatch or sounddevice
                    # Default values, will be overridden when we create the input stream
                    sample_rate = 44100  # Default, will be updated
                    channels = 2
                    print(f"Initial sample rate: {sample_rate} Hz (will be updated when input stream is created)")
                    
                    print(f"Using input device: {input_device_name} (index: {loopback_device})")
                    print(f"Sample rate: {sample_rate} Hz, Channels: {channels}")
                    
                    # Determine the actual device name to mute (remove loopback suffix if present)
                    if input_device_name:
                        # Extract base device name (remove "(WASAPI Loopback)" or similar suffixes)
                        base_device_name = input_device_name.replace(" (WASAPI Loopback)", "").replace("[Loopback]", "").strip()
                        # Also try to get from default_output_name if available
                        if 'default_output_name' in locals() and default_output_name:
                            device_to_mute_name = default_output_name
                        else:
                            device_to_mute_name = base_device_name
                        print(f"Device to mute: {device_to_mute_name}")
                    else:
                        # Fallback to default output name
                        if 'default_output_name' in locals() and default_output_name:
                            device_to_mute_name = default_output_name
                        else:
                            device_to_mute_name = None
                    
                    # Mute the device being captured from (only if not used for output)
                    # Smart muting: Don't mute if the default device is one of our output devices
                    if volume_control_available and device_to_mute_name:
                        try:
                            from audio_volume_control import mute_device_by_name, get_default_output_mute_state, get_default_device_name
                            
                            # Check if the default device is one of our output devices
                            default_device_name = get_default_device_name()
                            
                            # Get device names from device indices (not GUI variables - they're not accessible in thread)
                            device1_name = None
                            device2_name = None
                            if self.device1_index is not None:
                                try:
                                    device1_info = sd.query_devices(self.device1_index)
                                    device1_name = device1_info['name']
                                except:
                                    pass
                            if self.device2_index is not None:
                                try:
                                    device2_info = sd.query_devices(self.device2_index)
                                    device2_name = device2_info['name']
                                except:
                                    pass
                            
                            # Only mute if default device is NOT being used for output
                            should_mute = True
                            if default_device_name:
                                # Check if default device matches either output device
                                if device1_name and default_device_name.lower() in device1_name.lower():
                                    print(f"⚠ Skipping mute: Device 1 ({device1_name}) is the default output")
                                    should_mute = False
                                elif device2_name and default_device_name.lower() in device2_name.lower():
                                    print(f"⚠ Skipping mute: Device 2 ({device2_name}) is the default output")
                                    should_mute = False
                            
                            if should_mute:
                                # Try to get mute state of the specific device (fallback to default)
                                original_mute_state = get_default_output_mute_state()
                                print(f"Original mute state: {original_mute_state}")
                                
                                # Mute the specific device
                                if mute_device_by_name(device_to_mute_name):
                                    print(f"✓ Successfully muted device: {device_to_mute_name}")
                                else:
                                    # Fallback: try muting default device
                                    print(f"⚠ Could not mute specific device, trying default device...")
                                    if mute_default_output():
                                        print("✓ Default audio device muted (fallback)")
                                    else:
                                        print("⚠ Could not mute any audio device")
                            else:
                                print("ℹ Skipping mute to allow passthrough output to default device")
                                original_mute_state = None  # Don't restore mute state since we didn't mute
                        except Exception as e:
                            print(f"⚠ Error muting audio device '{device_to_mute_name}': {e}")
                            import traceback
                            traceback.print_exc()
                            volume_control_available = False
                    elif volume_control_available:
                        # No device name, try default
                        try:
                            from audio_volume_control import mute_default_output, get_default_output_mute_state
                            original_mute_state = get_default_output_mute_state()
                            if mute_default_output():
                                print("✓ Default audio device muted")
                            else:
                                print("⚠ Could not mute default audio device")
                        except Exception as e:
                            print(f"⚠ Error muting default audio: {e}")
                            volume_control_available = False
                    
                    # Update status based on ready mode
                    ready_mode = self.passthrough_ready_mode.get()
                    if ready_mode:
                        self.root.after(0, lambda: self.passthrough_status_label.config(
                            text=f"Ready - Capturing from: {input_device_name} (Waiting for audio...)", fg="green"
                        ))
                    else:
                        self.root.after(0, lambda: self.passthrough_status_label.config(
                            text=f"Capturing from: {input_device_name}", fg="blue"
                        ))
                    
                    # Prepare output devices
                    # Update volume cache from GUI values (before starting passthrough to avoid blocking)
                    vol1 = self.volume1_var.get() / 100.0
                    vol2 = self.volume2_var.get() / 100.0
                    with self._volume_cache_lock:
                        self._volume_cache[1] = vol1
                        self._volume_cache[2] = vol2
                    
                    devices_to_use = []
                    
                    # Robustly gather all selected devices
                    # This uses the helper method that parses the GUI selection text
                    # ensuring we get exactly what the user sees/selected
                    all_selected_devices = []
                    
                    # Safely call GUI method from thread (get_all_selected_devices uses .get() which is generally safe for reading strings, but ideally we'd pass this in)
                    # Since we're already locked or in a known state, valid here
                    try:
                        all_selected_devices = self.get_all_selected_devices()
                    except Exception as e:
                        print(f"Error getting selected devices: {e}")
                        # Fallback to old method if helper fails
                        if self.device1_index is not None:
                            all_selected_devices.append((1, self.device1_index, "Device 1"))
                        if self.device2_index is not None:
                            all_selected_devices.append((2, self.device2_index, "Device 2"))
                    
                    print(f"DEBUG: All selected devices: {all_selected_devices}")
                    
                    for device_num, device_idx, device_name in all_selected_devices:
                        # VALIDATION: Reject Phone/Mono devices
                        # This prevents the specific error user was seeing (PaErrorCode -9998 / invalid channels)
                        try:
                            dev_info = sd.query_devices(device_idx)
                            dev_channels = dev_info.get('max_output_channels', 0)
                            dev_name_real = dev_info.get('name', 'Unknown')
                            
                            is_invalid = False
                            error_reason = ""
                            
                            if 'headset' in dev_name_real.lower() and 'hands-free' in dev_name_real.lower():
                                is_invalid = True
                                error_reason = "Bluetooth Hands-Free mode (Mono Phone Quality)"
                            elif 'headset' in dev_name_real.lower() and dev_channels < 2:
                                is_invalid = True
                                error_reason = "Mono Headset Device"
                            elif dev_channels < 2:
                                is_invalid = True
                                error_reason = "Mono / Single Channel Device"
                                
                            if is_invalid:
                                print(f"❌ SKIPPING INVALID DEVICE: {dev_name_real} (Index {device_idx})")
                                print(f"   Reason: {error_reason}")
                                print(f"   Please select the 'Stereo' or 'Speaker' version of this device.")
                                continue # Skip this device
                                
                        except Exception as e:
                            print(f"Warning checking device {device_idx}: {e}")
                            
                        # Get volume for this device
                        vol = 1.0
                        if device_num == 1:
                            vol = vol1
                        elif device_num == 2:
                            vol = vol2
                        else:
                            # Dynamic device volume
                            # Find widget for this device number
                            for w in self.device_widgets:
                                if w['device_num'] == device_num:
                                    try:
                                        vol = w['volume_var'].get() / 100.0
                                    except:
                                        vol = 1.0
                                    break
                        
                        print(f"✓ Adding Device {device_num}: {device_name} (Index {device_idx}, Vol {vol:.2f})")
                        devices_to_use.append((device_idx, device_num, vol))
                    
                    if not devices_to_use:
                        print("⚠ NO VALID DEVICES SELECTED! Attempting fallback to defaults...")
                        # Fallback logic could go here, but for now just let it fail gracefully later
                    
                    # Shared audio buffer for all output streams
                    # Round 8: Optionally use FrontWalkBuffer for HPET-based timing and system clock playback
                    front_walk_buffer = None
                    hpet_timer = None
                    if self.use_front_walk_buffer and ROUND8_AVAILABLE:
                        try:
                            hpet_timer = get_hpet_timer()
                            # Calculate chunk interval from callback frames
                            chunk_interval_ms = (CALLBACK_FRAMES / sample_rate) * 1000.0  # ~23ms for 1024 frames at 44.1kHz
                            # Use 300ms buffer (configurable 200-500ms)
                            buffer_size_ms = 300.0
                            front_walk_buffer = FrontWalkBuffer(
                                buffer_size_ms=buffer_size_ms,
                                chunk_interval_ms=chunk_interval_ms,
                                sample_rate=sample_rate,
                                hpet_timer=hpet_timer
                            )
                            print(f"Round 8: FrontWalkBuffer enabled (buffer={buffer_size_ms}ms, chunk_interval={chunk_interval_ms:.1f}ms)")
                        except Exception as e:
                            print(f"Warning: Failed to initialize FrontWalkBuffer: {e}, falling back to standard buffer")
                            front_walk_buffer = None
                    
                    # Standard buffer (used when FrontWalkBuffer is disabled)
                    audio_buffer = []
                    buffer_lock = threading.Lock()
                    buffer_max_chunks = int(sample_rate * BUFFER_MAX_SECONDS / CALLBACK_FRAMES)
                    # Track read positions for each device to ensure both get audio
                    device_read_indices = {}  # device_num -> read_index
                    device_read_offsets = {}  # device_num -> read_index offset (for latency compensation)
                    # Track when buffer was last updated (for watchdog detection of stuck capture)
                    last_buffer_update_time = time.time()  # Timestamp of last chunk added to buffer
                    
                    # Volume boost for captured audio (to compensate for low Windows volume)
                    # WASAPI loopback captures audio AFTER Windows volume mixer, so low volume = low capture
                    # This boost amplifies the captured signal (1.0 = no boost, 2.0 = 2x, etc.)
                    # Note: Values > 1.0 may cause clipping if the original volume is already high
                    capture_volume_boost = 2.0  # Default 2x boost to compensate for typical low volume
                    
                    # Shared variable for actual measured sample rate (updated by capture thread)
                    # Stores both rounded rate (for device compatibility) and exact rate (for precision)
                    actual_measured_rate = {'rate': sample_rate, 'exact_rate': float(sample_rate), 'measured': False}
                    
                    # Shared flag to skip sample rate measurement for virtual cables (faster startup)
                    skip_sample_rate_measurement = {'skip': False}  # Will be set to True for virtual cables
                    
                    # Track audio levels for debugging
                    audio_level_counter = 0
                    last_level_print = time.time()
                    
                    # Track if audio has been detected (for ready mode indicator)
                    audio_detected_flag = {'detected': False}
                    
                    # Input callback for sounddevice - captures system audio
                    def input_callback(indata, frames, time_info, status):
                        nonlocal audio_level_counter, last_level_print, last_buffer_update_time
                        
                        if status:
                            print(f"Input status: {status}")
                        
                        # Check audio level (for debugging)
                        audio_level = np.abs(indata).max()
                        audio_level_counter += 1
                        
                        # Check if audio detected (for ready mode indicator)
                        ready_mode = self.passthrough_ready_mode.get()
                        if ready_mode and not audio_detected_flag['detected'] and audio_level > SILENCE_THRESHOLD:
                            audio_detected_flag['detected'] = True
                            # Update indicator to show audio is playing
                            def update_audio_detected():
                                self.ready_mode_indicator.config(
                                    text="🔊 AUDIO DETECTED - PLAYING NOW!\n\nAudio is being routed to selected devices instantly!",
                                    fg=self.colors['accent_primary'],
                                    bg=self.colors['bg_secondary']
                                )
                                self.ready_mode_indicator.update()  # Force update
                            self.root.after(0, update_audio_detected)
                            print("  ✓✓✓ READY MODE: Audio detected - playback started instantly! ✓✓✓")
                        
                        # Print audio level every 2 seconds
                        current_time = time.time()
                        if current_time - last_level_print > 2.0:
                            print(f"Audio input level: {audio_level:.4f} (max=1.0) - {'Audio detected!' if audio_level > SILENCE_THRESHOLD else 'No audio detected'}")
                            last_level_print = current_time
                        
                        # Convert to stereo (2 channels) for output compatibility
                        audio_data = indata.copy()
                        input_channels = audio_data.shape[1]
                        
                        if input_channels == 1:
                            # Convert mono to stereo by duplicating the channel
                            audio_data = np.column_stack((audio_data[:, 0], audio_data[:, 0]))
                        elif input_channels > 2:
                            # Convert multi-channel to stereo by taking first 2 channels
                            # or downmixing if needed
                            audio_data = audio_data[:, :2]
                        # If already 2 channels, use as-is
                        
                        # Store captured audio in shared buffer (always stereo now)
                        # Round 9: Distribute to fleet nodes if master mode (but still output locally)
                        if distributed_mode == "master" and self.master_node:
                            try:
                                self.master_node.distribute_audio_chunk(audio_data, sample_rate)
                            except Exception as e:
                                print(f"Error distributing audio chunk: {e}")
                        
                        # Round 8: Use FrontWalkBuffer with HPET timestamps if enabled
                        if front_walk_buffer is not None:
                            # Use HPET timestamp for precise timing
                            timestamp = hpet_timer.now()
                            front_walk_buffer.receive_chunk(audio_data, timestamp)
                            # Update timestamp for watchdog (using time.time() for compatibility)
                            last_buffer_update_time = time.time()
                        else:
                            # Standard buffer (backward compatible) - ALWAYS add to buffer for local output
                            with buffer_lock:
                                audio_buffer.append(audio_data)
                                # Limit buffer size to prevent memory issues
                                chunks_removed = 0
                                while len(audio_buffer) > buffer_max_chunks:
                                    audio_buffer.pop(0)  # Remove oldest chunk
                                    chunks_removed += 1
                                
                                # CRITICAL: Adjust read_index for all devices when chunks are removed from front
                                # This prevents desync and ensures devices stay synchronized with the buffer
                                if chunks_removed > 0:
                                    for device_num in device_read_indices:
                                        # Subtract removed chunks from read_index, but don't go below 0
                                        device_read_indices[device_num] = max(0, device_read_indices[device_num] - chunks_removed)
                                
                                # Update timestamp to track buffer activity (for watchdog)
                                last_buffer_update_time = time.time()
                    
                    # PyAudioWPatch capture thread (if using PyAudioWPatch)
                    def pyaudio_capture_thread():
                        """Capture audio using PyAudioWPatch and add to buffer."""
                        nonlocal sample_rate, buffer_max_chunks, last_buffer_update_time  # Access outer scope variables
                        try:
                            # CRITICAL: PyAudioWPatch reads variable chunk sizes (logs show 65536 frames)
                            # We'll read a large chunk and measure the actual sample rate
                            chunk_size = 65536  # Start with large chunk size - will adjust based on actual reads
                            audio_level_counter = 0
                            last_level_print = time.time()
                            read_count = 0
                            
                            # Silence detection: track consecutive silent chunks
                            consecutive_silent_chunks = 0
                            silence_threshold = SILENCE_THRESHOLD
                            max_silent_chunks = MAX_SILENT_CHUNKS
                            is_silent = False
                            
                            print("PyAudioWPatch capture thread started - beginning audio capture...")
                            
                            # Measure actual sample rate by timing chunk reads (skip for virtual cables)
                            chunk_times = []  # Track (time, samples) pairs
                            actual_input_sample_rate = sample_rate  # Will be measured
                            rate_measured = skip_sample_rate_measurement['skip']  # Skip if virtual cable
                            
                            if skip_sample_rate_measurement['skip']:
                                print("  ⚡ SKIPPING sample rate measurement (virtual cable - using device rate)")
                                # Mark as measured immediately with device rate
                                actual_measured_rate['measured'] = True
                                actual_measured_rate['rate'] = sample_rate
                                actual_measured_rate['exact_rate'] = float(sample_rate)  # Store exact rate
                            
                            last_chunk_time = time.time()  # Track when last chunk was read
                            consecutive_failures = 0
                            max_consecutive_failures = MAX_CONSECUTIVE_FAILURES
                            
                            while self.passthrough_active and pyaudio_stream is not None:
                                try:
                                    # Check if stream is active
                                    if not pyaudio_stream.is_active():
                                        print("⚠⚠⚠ WARNING: PyAudioWPatch stream is not active! Attempting restart...")
                                        consecutive_failures += 1
                                        if consecutive_failures >= max_consecutive_failures:
                                            print("⚠⚠⚠ Too many consecutive failures - exiting capture thread to trigger restart")
                                            break
                                        time.sleep(0.5)
                                        # Try to restart the stream
                                        try:
                                            pyaudio_stream.stop_stream()
                                            pyaudio_stream.close()
                                        except:
                                            pass
                                        time.sleep(0.5)
                                        # Stream will be recreated by outer thread - exit this thread
                                        print("⚠⚠⚠ Capture thread exiting - stream will be restarted")
                                        break
                                    
                                    # REMOVED: CAPTURE_TIMEOUT check - don't exit on silence
                                    # The outer watchdog (CAPTURE_STUCK_TIMEOUT) handles stuck detection
                                    # Silence is normal and shouldn't cause capture to stop
                                    
                                    # Read audio data from PyAudio stream
                                    read_start_time = time.time()
                                    audio_data = pyaudio_stream.read(chunk_size, exception_on_overflow=False)
                                    read_end_time = time.time()
                                    read_count += 1
                                    last_chunk_time = read_start_time  # Update last chunk time
                                    consecutive_failures = 0  # Reset failure counter on successful read
                                    
                                    if read_count == 1:
                                        print(f"✓ Successfully read first audio chunk ({len(audio_data)} bytes)")
                                    
                                    # Convert to numpy array
                                    audio_array = np.frombuffer(audio_data, dtype=np.int16)
                                    
                                    # Convert to float32 and normalize
                                    audio_float = audio_array.astype(np.float32) / 32768.0
                                    
                                    # Apply volume boost to compensate for low Windows volume
                                    # WASAPI loopback captures AFTER Windows volume mixer, so we need to boost
                                    # if the system volume is low. This helps capture audio even when volume is down.
                                    if capture_volume_boost != 1.0:
                                        audio_float = audio_float * capture_volume_boost
                                        # Clip to prevent distortion (values should be between -1.0 and 1.0)
                                        audio_float = np.clip(audio_float, -1.0, 1.0)
                                    
                                    # Calculate expected samples per channel
                                    bytes_per_sample = 2  # int16
                                    samples_total = len(audio_array)
                                    
                                    # CRITICAL: PyAudioWPatch loopback always returns stereo (2 channels) regardless of stream config
                                    # The stream may report 8 channels, but the actual audio data is always 2 channels (stereo)
                                    actual_channels = 2
                                    expected_samples_per_channel = samples_total // actual_channels
                                    
                                    # Measure actual sample rate from timing (first 10 chunks)
                                    if not rate_measured and read_count <= 10:
                                        # Store frames per channel using ACTUAL channel count (2 for stereo)
                                        # samples_total is the total number of samples (e.g., 262144 for 131072 frames * 2 channels)
                                        # For rate calculation, we need frames per channel per second
                                        frames_per_channel = samples_total // actual_channels
                                        if read_count <= 3:
                                            print(f"  Chunk {read_count} measurement: samples_total={samples_total}, stream_channels={channels}, actual_channels={actual_channels}, frames_per_channel={frames_per_channel}")
                                        chunk_times.append((read_start_time, frames_per_channel))
                                        
                                        # Calculate actual sample rate when we have 10 chunks
                                        if read_count == 10:
                                            # Calculate actual sample rate
                                            if len(chunk_times) >= 2:
                                                # Time span is wall-clock time between first and last chunk reads
                                                time_span = chunk_times[-1][0] - chunk_times[0][0]
                                                total_frames = sum(frames for _, frames in chunk_times)
                                                
                                                # Expected audio duration at the current sample rate
                                                expected_duration = total_frames / sample_rate
                                                
                                                if time_span > 0:
                                                    # CRITICAL: The measurement is based on wall-clock time between reads,
                                                    # but this can be affected by buffering, system load, etc.
                                                    # We need to be more conservative and only trust measurements
                                                    # that are significantly different from expected.
                                                    
                                                    # Calculate what the rate would be based on wall-clock time
                                                    wall_clock_rate = total_frames / time_span
                                                    
                                                    # Calculate the ratio between wall-clock time and expected audio duration
                                                    time_ratio = time_span / expected_duration
                                                    
                                                    # If the time ratio is close to 1.0, the rate is correct
                                                    # If time_ratio > 1.0, chunks are arriving slower (input rate is lower)
                                                    # If time_ratio < 1.0, chunks are arriving faster (input rate is higher)
                                                    
                                                    # However, buffering can cause chunks to arrive in bursts,
                                                    # making wall-clock time unreliable. We need to be very conservative.
                                                    # Only trust measurements if they're significantly different.
                                                    
                                                    if abs(time_ratio - 1.0) > SAMPLE_RATE_MEASUREMENT_THRESHOLD:
                                                        # Significant difference - use measured rate
                                                        measured_rate = wall_clock_rate
                                                        print(f"\n  Sample rate measurement after {read_count} chunks:")
                                                        print(f"    Wall-clock time span: {time_span:.3f} seconds")
                                                        print(f"    Expected audio duration at {sample_rate} Hz: {expected_duration:.3f} seconds")
                                                        print(f"    Time ratio: {time_ratio:.3f} ({'slower' if time_ratio > 1.0 else 'faster'})")
                                                        print(f"    Total frames: {total_frames} (across all chunks)")
                                                        print(f"    Calculated rate: {measured_rate:.1f} Hz")
                                                        print(f"    ⚠ Large difference detected - using measured rate")
                                                    else:
                                                        # Close to expected - measurement might be affected by buffering
                                                        # Use the expected rate (measurement is unreliable)
                                                        measured_rate = sample_rate
                                                        threshold_pct = int(SAMPLE_RATE_MEASUREMENT_THRESHOLD * 100)
                                                        print(f"\n  Sample rate measurement after {read_count} chunks:")
                                                        print(f"    Wall-clock time span: {time_span:.3f} seconds")
                                                        print(f"    Expected audio duration at {sample_rate} Hz: {expected_duration:.3f} seconds")
                                                        print(f"    Time ratio: {time_ratio:.3f} (within {threshold_pct}% tolerance)")
                                                        print(f"    Total frames: {total_frames} (across all chunks)")
                                                        print(f"    Using expected rate: {measured_rate:.1f} Hz (measurement may be affected by buffering)")
                                                    
                                                    # Use measured rate directly for maximum accuracy (preserve exact rate)
                                                    # Round to nearest integer for device compatibility, but store exact value
                                                    actual_input_sample_rate = int(round(measured_rate))
                                                    # Store the EXACT measured rate (float) for maximum precision
                                                    exact_measured_rate = measured_rate
                                                    print(f"    Measured exact rate: {exact_measured_rate:.6f} Hz")
                                                    print(f"    Using rounded rate: {actual_input_sample_rate} Hz (for device compatibility)")
                                                    
                                                    # Always update to use measured rate (even if close, use exact measurement)
                                                    if abs(actual_input_sample_rate - sample_rate) > 0.5:  # More than 0.5 Hz difference
                                                        print(f"\n⚠⚠⚠ CRITICAL SAMPLE RATE MISMATCH DETECTED! ⚠⚠⚠")
                                                        print(f"  Expected: {sample_rate} Hz")
                                                        print(f"  Measured exact: {exact_measured_rate:.6f} Hz")
                                                        print(f"  Measured rounded: {actual_input_sample_rate} Hz")
                                                        print(f"  Speed factor: {exact_measured_rate/sample_rate:.6f}x")
                                                        print(f"  ⚠⚠⚠ This explains the speed issue! ⚠⚠⚠")
                                                        print(f"  ⚠⚠⚠ Output streams need to be restarted with exact measured rate! ⚠⚠⚠\n")
                                                    else:
                                                        print(f"✓ Sample rate verified: {actual_input_sample_rate} Hz (exact: {exact_measured_rate:.6f} Hz)")
                                                    
                                                    # ALWAYS update to measured rate for exact speed matching
                                                    # Store both exact and rounded rates
                                                    sample_rate = actual_input_sample_rate
                                                    actual_measured_rate['rate'] = actual_input_sample_rate
                                                    actual_measured_rate['exact_rate'] = exact_measured_rate  # Store exact rate
                                                    actual_measured_rate['measured'] = True
                                                    # Update buffer_max_chunks with new rate
                                                    buffer_max_chunks = int(sample_rate * BUFFER_MAX_SECONDS / CALLBACK_FRAMES)
                                                    rate_measured = True
                                                    print(f"  ✓ Updated sample_rate to {sample_rate} Hz (exact: {exact_measured_rate:.6f} Hz) for perfect speed matching")
                                    
                                    # Reshape for channels (use actual_channels from audio shape, not stream config)
                                    if actual_channels == 2:
                                        if samples_total % 2 == 0:
                                            audio_float = audio_float.reshape((-1, 2))
                                        else:
                                            # Odd number of samples, pad with zero
                                            audio_float = np.append(audio_float, 0.0)
                                            audio_float = audio_float.reshape((-1, 2))
                                    else:
                                        # Convert mono to stereo
                                        audio_float = np.column_stack((audio_float, audio_float))
                                    
                                    # Check audio level (for debugging)
                                    audio_level = np.abs(audio_float).max()
                                    audio_mean = np.abs(audio_float).mean()
                                    audio_level_counter += 1
                                    current_time = time.time()
                                    
                                    # Log first few chunks for debugging
                                    if read_count <= 5:
                                        print(f"  Chunk {read_count}: shape={audio_float.shape}, max={audio_level:.4f}, mean={audio_mean:.4f}, bytes={len(audio_data)}")
                                    
                                    # Silence detection: check if this chunk is silent
                                    chunk_is_silent = audio_level < silence_threshold
                                    
                                    if chunk_is_silent:
                                        consecutive_silent_chunks += 1
                                        if consecutive_silent_chunks >= max_silent_chunks and not is_silent:
                                            is_silent = True
                                            print(f"⚠ SILENCE DETECTED: {consecutive_silent_chunks} consecutive silent chunks - limiting buffer size (capture continues)")
                                            print(f"  Capture will continue - audio will resume instantly when detected")
                                    else:
                                        # Audio detected - reset silence counter
                                        if is_silent:
                                            print(f"✓ AUDIO RESUMED: Input level {audio_level:.4f} - resuming buffer writes")
                                        consecutive_silent_chunks = 0
                                        is_silent = False
                                    
                                    # Check if audio detected (for ready mode indicator)
                                    ready_mode = self.passthrough_ready_mode.get()
                                    if ready_mode and not audio_detected_flag['detected'] and audio_level > SILENCE_THRESHOLD:
                                        audio_detected_flag['detected'] = True
                                        # Update indicator to show audio is playing
                                        def update_audio_detected():
                                            self.ready_mode_indicator.config(
                                                text="🔊 AUDIO DETECTED - PLAYING NOW!\n\nAudio is being routed to selected devices instantly!",
                                                fg=self.colors['accent_primary'],
                                                bg=self.colors['bg_secondary']
                                            )
                                            self.ready_mode_indicator.update()  # Force update
                                        self.root.after(0, update_audio_detected)
                                        print("  ✓✓✓ READY MODE: Audio detected - playback started instantly! ✓✓✓")
                                    
                                    if current_time - last_level_print > 2.0:
                                        with buffer_lock:
                                            buffer_size_info = len(audio_buffer)
                                        status = "✓ AUDIO DETECTED!" if audio_level > SILENCE_THRESHOLD else "✗ No audio detected"
                                        if is_silent:
                                            status += " (SILENCE - not buffering)"
                                        print(f"PyAudioWPatch input level: {audio_level:.4f} (max=1.0), mean={audio_mean:.4f} - {status}")
                                        print(f"  Chunks read: {read_count}, Buffer size: {buffer_size_info} chunks, Shape: {audio_float.shape}")
                                        if audio_level > SILENCE_THRESHOLD:
                                            print(f"  ✓✓✓ AUDIO IS BEING CAPTURED! ✓✓✓")
                                        last_level_print = current_time
                                    
                                    # Convert to stereo (2 channels) for output compatibility
                                    if audio_float.shape[1] != 2:
                                        if audio_float.shape[1] == 1:
                                            audio_float = np.column_stack((audio_float[:, 0], audio_float[:, 0]))
                                        elif audio_float.shape[1] > 2:
                                            audio_float = audio_float[:, :2]
                                    
                                    # Add to buffer - but limit buffer size when silent to prevent memory issues
                                    # When silent, keep a small buffer (2-3 chunks) in case audio resumes quickly
                                    # This is important when switching audio sources - audio may resume momentarily
                                    # CRITICAL: Always update last_buffer_update_time to prevent watchdog from triggering
                                    # even during silence - the capture thread must continue running
                                    with buffer_lock:
                                        current_buffer_size = len(audio_buffer)
                                        
                                    # Round 9: Distribute to fleet nodes if master mode (but still output locally)
                                    if distributed_mode == "master" and self.master_node:
                                        try:
                                            self.master_node.distribute_audio_chunk(audio_float, sample_rate)
                                        except Exception as e:
                                            print(f"Error distributing audio chunk: {e}")
                                    
                                    # Round 8: Use FrontWalkBuffer if enabled
                                    if front_walk_buffer is not None:
                                        # Use HPET timestamp for precise timing
                                        timestamp = hpet_timer.now()
                                        front_walk_buffer.receive_chunk(audio_float, timestamp)
                                        # Update timestamp for watchdog (using time.time() for compatibility)
                                        last_buffer_update_time = time.time()
                                    else:
                                        # Standard buffer (backward compatible) - ALWAYS add to buffer for local output
                                        if not is_silent:
                                            # Normal buffering - add chunk
                                            with buffer_lock:
                                                audio_buffer.append(audio_float)
                                                chunks_removed = 0
                                                while len(audio_buffer) > buffer_max_chunks:
                                                    audio_buffer.pop(0)
                                                    chunks_removed += 1
                                                
                                                # CRITICAL: Adjust read_index for all devices when chunks are removed from front
                                                # This prevents desync and ensures devices stay synchronized with the buffer
                                                if chunks_removed > 0:
                                                    for device_num in device_read_indices:
                                                        # Subtract removed chunks from read_index, but don't go below 0
                                                        device_read_indices[device_num] = max(0, device_read_indices[device_num] - chunks_removed)
                                                
                                                # Update timestamp to track buffer activity (for watchdog)
                                                last_buffer_update_time = time.time()
                                        else:
                                            # Silent - still capture and buffer to maintain continuity
                                            # Always buffer at least 1 chunk to keep capture active and prevent watchdog issues
                                            # This ensures audio resumes instantly when it starts again
                                            with buffer_lock:
                                                # Always add chunk during silence to keep capture active
                                                # Limit buffer to 5 chunks when silent to prevent memory issues
                                                audio_buffer.append(audio_float)
                                                chunks_removed = 0
                                                while len(audio_buffer) > 5:  # Limit to 5 chunks when silent (was 3)
                                                    audio_buffer.pop(0)
                                                    chunks_removed += 1
                                                
                                                # CRITICAL: Adjust read_index for all devices when chunks are removed from front
                                                # This prevents desync and ensures devices stay synchronized with the buffer
                                                if chunks_removed > 0:
                                                    for device_num in device_read_indices:
                                                        # Subtract removed chunks from read_index, but don't go below 0
                                                        device_read_indices[device_num] = max(0, device_read_indices[device_num] - chunks_removed)
                                                
                                                # CRITICAL: Always update timestamp even during silence
                                                # This prevents watchdog from thinking capture is stuck
                                                last_buffer_update_time = time.time()
                                except Exception as e:
                                    if self.passthrough_active:
                                        print(f"Error reading from PyAudio stream: {e}")
                                        import traceback
                                        traceback.print_exc()
                                    break
                        except Exception as e:
                            print(f"PyAudio capture thread error: {e}")
                            import traceback
                            traceback.print_exc()
                    
                    # Create output callbacks for each device
                    # Track output levels for debugging (shared across all callbacks)
                    output_level_counters = {}
                    output_level_timers = {}
                    
                    # Store remainder buffers in outer scope so they persist across callbacks
                    remainder_buffers = {}  # device_num -> remainder array
                    stream_start_times = {}  # device_num -> absolute start time (set when stream starts)
                    device_start_times = {}  # device_num -> delay in seconds (None = no delay) - initialized later
                    global_stream_start_time = [None]  # Use list to allow modification in nested scope
                    
                    # APPROACH 2: Threading Event Synchronization - ensure all callbacks are ready before starting
                    sync_events = {}  # device_num -> threading.Event (set when callback is ready)
                    callback_ready_flags = {}  # device_num -> bool (True when callback has been called at least once)
                    for device_num, _, _ in devices_to_use:
                        sync_events[device_num] = threading.Event()
                        callback_ready_flags[device_num] = False
                    
                    # APPROACH 4: Hardware timestamp synchronization
                    global_start_dac_time = [None]  # Hardware DAC timestamp when all devices should start
                    
                    def make_output_callback(device_num):
                        # Initialize counters for this device
                        if device_num not in output_level_counters:
                            output_level_counters[device_num] = 0
                            output_level_timers[device_num] = time.time()
                        
                        # Track if delay has passed (optimization to prevent repeated checks)
                        delay_passed = [False]
                        
                        def output_callback(outdata, frames, time_info, status):
                            # CRITICAL: Increment callback counter FIRST so it's available throughout the callback
                            # Initialize counter if needed
                            if device_num not in output_level_counters:
                                output_level_counters[device_num] = 0
                            output_level_counters[device_num] += 1
                            callback_num = output_level_counters[device_num]
                            
                            # CRITICAL: Get delay time for this device INSIDE callback (not in closure)
                            # This ensures we get the value AFTER device_start_times is populated
                            device_delay_seconds = device_start_times.get(device_num)  # Delay in seconds (None = no delay)
                            
                            # CRITICAL: Check time-based delay FIRST, before any locks or other processing
                            # This ensures ALL devices wait until their calculated start time BEFORE outputting audio
                            # This prevents stuttering from delay checks happening inside locks
                            # Only check if delay hasn't passed yet (performance optimization)
                            if not delay_passed[0]:
                                current_time = time.time()
                                
                                # global_stream_start_time[0] should already be set before streams start
                                if global_stream_start_time[0] is not None:
                                    # Calculate device's absolute start time
                                    if device_delay_seconds is not None and device_delay_seconds > 0:
                                        # Device has additional delay - add it to global start time
                                        device_absolute_start_time = global_stream_start_time[0] + device_delay_seconds
                                    else:
                                        # Device has no additional delay - start at global start time
                                        device_absolute_start_time = global_stream_start_time[0]
                                    
                                    if current_time < device_absolute_start_time:
                                        # Still waiting - output silence and return immediately (no locks, no processing)
                                        outdata[:] = np.zeros((frames, outdata.shape[1]), dtype=np.float32)
                                        return
                                    else:
                                        # Start time has arrived - mark it so we don't check again
                                        delay_passed[0] = True
                                        if callback_num == 1:  # First callback after delay
                                            if device_delay_seconds is not None and device_delay_seconds > 0:
                                                actual_delay = (current_time - global_stream_start_time[0]) * 1000.0
                                                print(f"  ✓ Device {device_num} delay complete: {actual_delay:.1f}ms (expected: {device_delay_seconds*1000:.1f}ms)")
                                            else:
                                                actual_wait = (current_time - global_stream_start_time[0]) * 1000.0
                                                print(f"  ✓ Device {device_num} started at global start time: {actual_wait:.1f}ms wait (no additional delay)")
                                else:
                                    # Fallback: if global_stream_start_time not set, initialize it
                                    if 'output_buffer_dac_time' in time_info and time_info['output_buffer_dac_time'] is not None:
                                        global_stream_start_time[0] = time_info['output_buffer_dac_time']
                                    else:
                                        global_stream_start_time[0] = time.time()
                                    # Don't wait if we just initialized - start immediately
                                    delay_passed[0] = True
                            
                            # APPROACH 2: Threading Event Synchronization - mark this callback as ready
                            # Defensive: Initialize if not exists (in case callback runs before initialization)
                            if device_num not in callback_ready_flags:
                                callback_ready_flags[device_num] = False
                            if device_num not in sync_events:
                                sync_events[device_num] = threading.Event()
                            
                            if not callback_ready_flags[device_num]:
                                callback_ready_flags[device_num] = True
                                sync_events[device_num].set()
                                
                                # Wait for ALL devices to be ready (first callback received)
                                # Get list of device numbers from devices_to_use safely
                                try:
                                    device_nums = [d_num for d_num, _, _ in devices_to_use]
                                except:
                                    # Fallback: use all keys in callback_ready_flags
                                    device_nums = list(callback_ready_flags.keys())
                                
                                all_ready = all(callback_ready_flags.get(d_num, False) for d_num in device_nums)
                                
                                if callback_num == 1:
                                    print(f"  Device {device_num} callback #1: Ready flag set (waiting for other devices...)")
                                
                                if all_ready:
                                    # All callbacks are now active - set hardware timestamp if available
                                    if global_start_dac_time[0] is None:
                                        # APPROACH 4: Use hardware timestamp for precise synchronization
                                        # Set global start time 50ms in the future to allow all streams to stabilize
                                        if 'output_buffer_dac_time' in time_info and time_info['output_buffer_dac_time'] is not None:
                                            global_start_dac_time[0] = time_info['output_buffer_dac_time'] + 0.05
                                            print(f"\n  ✓✓✓ ALL DEVICES READY - HARDWARE SYNC ACTIVE ✓✓✓")
                                            print(f"  Global start DAC time: {global_start_dac_time[0]:.6f} (50ms in future)")
                                            print(f"  All {len(device_nums)} device callbacks are active\n")
                                        else:
                                            # Fallback to system time if hardware timestamp not available
                                            if global_stream_start_time[0] is None:
                                                global_stream_start_time[0] = time.time() + 0.05
                                                print(f"\n  ✓✓✓ ALL DEVICES READY - SOFTWARE SYNC ACTIVE ✓✓✓")
                                                print(f"  Global start time: {global_stream_start_time[0]:.6f} (50ms in future)")
                                                print(f"  All {len(device_nums)} device callbacks are active\n")
                            
                            # Multi-Bluetooth Sync: Record callback for jitter measurement
                            if MULTI_BLUETOOTH_SYNC_AVAILABLE and self.jitter_measurer:
                                # Find device index for this device_num
                                device_idx = None
                                for dev_idx, dev_num, _ in devices_to_use:
                                    if dev_num == device_num:
                                        device_idx = dev_idx
                                        break
                                if device_idx is not None:
                                    self.jitter_measurer.record_callback(device_idx)
                            
                            # Variables audio_buffer, buffer_lock, device_read_indices, and remainder_buffers
                            # are captured from the outer scope via closure
                            if status:
                                print(f"Output status (Device {device_num}, callback #{callback_num}): {status}")
                            
                            # CRITICAL: Always initialize outdata to zeros first to prevent garbage audio
                            outdata.fill(0.0)
                            
                            # Get current volume for this device (from thread-safe cache to avoid blocking during window movement)
                            try:
                                with self._volume_cache_lock:
                                    current_volume = self._volume_cache.get(device_num, 1.0)
                            except:
                                current_volume = 1.0  # Default to full volume if cache access fails
                            
                            # Round 9: Use FleetNode if in fleet mode
                            if distributed_mode == "fleet" and self.fleet_node and self.fleet_node.connected:
                                chunk_data, sequence, wait_time = self.fleet_node.get_chunk_to_play(frames)
                                if chunk_data is not None:
                                    # Chunk ready to play - apply volume and output
                                    if current_volume != 1.0:
                                        chunk_data = chunk_data * current_volume
                                    outdata[:] = chunk_data
                                    return
                                else:
                                    # No chunk ready - output silence
                                    outdata[:] = np.zeros((frames, outdata.shape[1]), dtype=np.float32)
                                    return
                            
                            # Round 8: Use FrontWalkBuffer if enabled (system clock-based playback)
                            if front_walk_buffer is not None:
                                # Get chunk based on system clock
                                chunk_data, sequence, wait_time = front_walk_buffer.get_chunk_to_play(frames)
                                
                                if chunk_data is not None:
                                    # Chunk ready to play - apply volume and output
                                    if current_volume != 1.0:
                                        chunk_data = chunk_data * current_volume
                                    outdata[:] = chunk_data
                                    return
                                else:
                                    # No chunk ready - output silence
                                    outdata[:] = np.zeros((frames, outdata.shape[1]), dtype=np.float32)
                                    return
                            
                            # Standard buffer path (backward compatible)
                            # Get audio from shared buffer
                            chunk = None
                            buffer_size = 0
                            chunk_from_remainder = False  # Track if chunk came from remainder vs buffer
                            
                            # CRITICAL: Check for remainder FIRST, before entering lock
                            # This ensures we use remainder if it exists, and only get new chunk if needed
                            # Get fresh reference to remainder
                            remainder = remainder_buffers.get(device_num)
                            has_remainder = (remainder is not None) and (len(remainder) > 0 if remainder is not None else False)
                            
                            micro_delay_needed = False
                            micro_skip_needed = False
                            
                            try:
                                with buffer_lock:
                                    buffer_size = len(audio_buffer)
                                    
                                    # Initialize read index for this device if not exists
                                    # CRITICAL: This should already be set during offset calculation
                                    # If not set, default to 0 (no wait, start immediately)
                                    if device_num not in device_read_indices:
                                        device_read_indices[device_num] = 0
                                        print(f"⚠ Device {device_num} read_index not initialized - defaulting to 0")
                                    
                                    read_index = device_read_indices[device_num]
                                    
                                    # Sync devices smoothly using micro-adjustments instead of entire chunks
                                    drift_check_interval = 60  # ~1.3x/sec
                                    if callback_num % drift_check_interval == 0 and len(devices_to_use) > 1:
                                        all_indices = {dev[1]: device_read_indices.get(dev[1], 0) for dev in devices_to_use}
                                        min_index = min(all_indices.values())
                                        max_index = max(all_indices.values())
                                        device_drift = max_index - min_index
                                        
                                        if device_drift > 0:
                                            if read_index == max_index:
                                                # This device is ahead. Signal to apply a tiny delay (stretch audio)
                                                micro_delay_needed = True
                                                if callback_num % 300 == 0:
                                                    print(f"  Device {device_num}: Fast device (ahead by {device_drift} chunks) -> applying micro-stretch")
                                            elif read_index < max_index - 1:
                                                # Extremely behind (>1 chunk). Unrecoverable with micro-skips, jump forward.
                                                safe_max = buffer_size - 1 if buffer_size > 0 else read_index
                                                new_index = min(read_index + 1, max_index, safe_max)
                                                if new_index > read_index:
                                                    device_read_indices[device_num] = new_index
                                                    if callback_num % 300 == 0:
                                                        print(f"  Device {device_num}: Extremely slow -> Sync +1 chunk (was {max_index - read_index} behind)")
                                            elif read_index < max_index:
                                                # Slightly behind (1 chunk). Signal to apply a tiny skip (squish audio)
                                                micro_skip_needed = True
                                                if callback_num % 300 == 0:
                                                    print(f"  Device {device_num}: Slow device -> applying micro-squish to catch up")
                                        
                                        if callback_num % 400 == 0 and device_drift > 0:
                                            print(f"  Multi-device drift: {device_drift} chunks (min: {min_index}, max: {max_index})")
                                    
                                    # Hardware timestamps used only for start delay; no expected_chunks correction here
                                    # so we have one source of truth (slowest device) and no conflicting corrections.
                                    
                                    # APPROACH 4 (continued): Hardware timestamp synchronization (after time-based delay is handled)
                                    if global_start_dac_time[0] is not None:
                                        # Use hardware timestamp if available for fine-grained sync
                                        if 'output_buffer_dac_time' in time_info and time_info['output_buffer_dac_time'] is not None:
                                            current_dac_time = time_info['output_buffer_dac_time']
                                            # Calculate device-specific start time (already includes delay if device_delay_seconds was set)
                                            device_start_dac_time = global_start_dac_time[0]
                                            if device_delay_seconds is not None and device_delay_seconds > 0:
                                                device_start_dac_time += device_delay_seconds
                                            
                                            if current_dac_time < device_start_dac_time:
                                                # Still waiting for hardware sync time (more precise than system time)
                                                wait_remaining_dac = (device_start_dac_time - current_dac_time) * 1000.0
                                                if callback_num == 1:
                                                    print(f"  Device {device_num} callback #1: Hardware DAC sync active (waiting {wait_remaining_dac:.2f}ms more)")
                                                elif callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                                    wait_remaining = (device_start_dac_time - current_dac_time) * 1000.0
                                                    print(f"  Device {device_num} callback #{callback_num}: Hardware sync delay active (waiting {wait_remaining:.1f}ms more)")
                                                # Output silence while waiting
                                                outdata[:] = np.zeros((frames, outdata.shape[1]), dtype=np.float32)
                                                return
                                            elif callback_num == 1 and device_delay_seconds is not None and device_delay_seconds > 0:
                                                # First callback after hardware delay - verify timing
                                                actual_delay_dac = (current_dac_time - global_start_dac_time[0]) * 1000.0
                                                print(f"  ✓ Hardware DAC sync: Device {device_num} delay applied ({actual_delay_dac:.2f}ms)")
                                    
                                    # If read_index is negative, wait for buffer to build up
                                    # This implements latency compensation by delaying start
                                    if read_index < 0:
                                        # Need to wait for more chunks
                                        required_chunks = abs(read_index)
                                        if buffer_size >= required_chunks:
                                            # Buffer has enough chunks, start reading from position 0
                                            # CRITICAL: All devices read from position 0 to stay synchronized
                                            # The wait was just to ensure buffer has enough data for latency compensation
                                            start_position = 0
                                            device_read_indices[device_num] = start_position
                                            read_index = start_position
                                            if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                                print(f"  Device {device_num} callback #{callback_num}: Buffer ready, starting read from index {start_position} (was waiting for {required_chunks} chunks to build up)")
                                        else:
                                            # Still waiting for buffer to build up
                                            if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                                print(f"  Device {device_num} callback #{callback_num}: Waiting for buffer (need {required_chunks} chunks, have {buffer_size})")
                                            # Output silence while waiting
                                            outdata[:] = np.zeros((frames, outdata.shape[1]), dtype=np.float32)
                                            return
                                    
                                    # Only get chunk from buffer if we DON'T have a remainder
                                    # CRITICAL: Ensure read_index is within bounds
                                    if not has_remainder and read_index < len(audio_buffer) and read_index < buffer_size:
                                        # No remainder, so get a new chunk from buffer
                                        # Note: chunks from buffer are 65536 frames (much larger than callback size)
                                        chunk = audio_buffer[read_index].copy()
                                        # Advance read_index immediately when we get a new chunk
                                        # BUT: Don't advance beyond buffer_size to prevent desync
                                        new_read_index = min(read_index + 1, buffer_size)
                                        device_read_indices[device_num] = new_read_index
                                    elif not has_remainder and read_index >= buffer_size:
                                        # Read index is beyond available buffer - wait for more data
                                        # Don't advance, just output silence
                                        chunk = None
                                        # Don't output zeros yet - we'll do that below if chunk is None
                                        if callback_num % DEBUG_LOG_EVERY_N_CALLBACKS_SPARSE == 0:
                                            print(f"  Device {device_num} callback #{callback_num}: Waiting for buffer (read_index={read_index} >= buffer_size={buffer_size})")
                                        # Reset read_index to a safe position if it's way beyond buffer
                                        if read_index > buffer_size + 5:
                                            # Way too far ahead - reset to near end of buffer
                                            device_read_indices[device_num] = max(0, buffer_size - 2)
                                            if callback_num % DEBUG_LOG_EVERY_N_CALLBACKS_SPARSE == 0:
                                                print(f"  Device {device_num} callback #{callback_num}: Reset read_index from {read_index} to {device_read_indices[device_num]} (was too far ahead)")
                                    elif has_remainder:
                                        # We have a remainder - but only use it if we're still within buffer bounds
                                        # If read_index >= buffer_size, we're ahead of available data - don't use remainder
                                        # This prevents desync when one device gets ahead
                                        if read_index >= buffer_size:
                                            # Ahead of buffer - don't use remainder, wait for new chunks
                                            chunk = None
                                            if callback_num % DEBUG_LOG_EVERY_N_CALLBACKS_SPARSE == 0:
                                                print(f"  Device {device_num} callback #{callback_num}: Has remainder but read_index={read_index} >= buffer_size={buffer_size} - waiting for new chunks (preventing desync)")
                                        else:
                                            # Within bounds - remainder will be used in processing, don't get new chunk
                                            chunk = None
                                            if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS or callback_num % DEBUG_LOG_EVERY_N_CALLBACKS == 0:
                                                rem_size = len(remainder) if remainder is not None else 0
                                                print(f"  Device {device_num} callback #{callback_num}: Has remainder ({rem_size} frames), will use it (read_index={read_index}, buffer_size={buffer_size})")
                                    else:
                                        # No data available and no remainder
                                        chunk = None
                                        if callback_num % DEBUG_LOG_EVERY_N_CALLBACKS_SPARSE == 0:
                                            print(f"  Device {device_num} callback #{callback_num}: No data available (read_index={read_index}, buffer_size={buffer_size})")
                                    
                                    # CRITICAL: Don't do buffer cleanup inside the lock - it causes devices to get stuck
                                    # Buffer cleanup will be done outside the lock, less frequently
                            except Exception as e:
                                print(f"ERROR in output_callback buffer access for Device {device_num} (callback #{callback_num}): {e}")
                                import traceback
                                traceback.print_exc()
                                # Output silence on error
                                outdata[:] = np.zeros((frames, outdata.shape[1]), dtype=np.float32)
                                return
                            
                            # CRITICAL: Process micro-adjustments using pure numpy continuous resampling
                            # This completely prevents hardware clock drift from causing stuttering or echoes.
                            if chunk is not None and len(chunk) > 0 and (micro_delay_needed or micro_skip_needed):
                                try:
                                    original_frames = len(chunk)
                                    # Adjust by ~0.1% speed to allow catchup without pitch distortion
                                    adjustment_frames = max(1, original_frames // 1000) 
                                    
                                    if micro_delay_needed:
                                        # Stretch audio: target frames > original frames
                                        target_frames = original_frames + adjustment_frames
                                    else:
                                        # Squish audio: target frames < original frames
                                        target_frames = original_frames - adjustment_frames
                                        
                                    # Create pure numpy interpolation space
                                    old_indices = np.linspace(0, original_frames - 1, original_frames)
                                    new_indices = np.linspace(0, original_frames - 1, target_frames)
                                    
                                    resampled_chunk = np.zeros((target_frames, chunk.shape[1]), dtype=np.float32)
                                    for channel in range(chunk.shape[1]):
                                        resampled_chunk[:, channel] = np.interp(new_indices, old_indices, chunk[:, channel])
                                        
                                    chunk = resampled_chunk
                                    
                                    if callback_num % 300 == 0:
                                        action = "Stretched" if micro_delay_needed else "Squished"
                                        print(f"  Device {device_num}: {action} {original_frames} -> {target_frames} frames (drift resample)")
                                except Exception as e:
                                    print(f"ERROR in micro-resample for Device {device_num}: {e}")
                                    # On failure, just use original chunk unaltered

                            # CRITICAL: Buffer cleanup is DISABLED - let buffer_max_chunks handle it
                            # The buffer_max_chunks limit will automatically remove old chunks when buffer gets too large
                            # This prevents underruns when devices consume chunks faster than they're added
                            
                            # CRITICAL: Process remainder FIRST (before processing chunk from buffer)
                            # This must happen immediately after the lock, using the remainder we checked before the lock
                            # BUT: Don't use remainder if read_index >= buffer_size (we're ahead of available data)
                            # In that case, wait for new chunks to maintain synchronization
                            # Get current read_index and buffer_size to check bounds
                            # (read_index might have been updated inside the lock, so get fresh value)
                            with buffer_lock:
                                current_read_index = device_read_indices.get(device_num, 0)
                                current_buffer_size = len(audio_buffer)
                            
                            # Only use remainder if we're still within buffer bounds
                            # This prevents desync when one device gets ahead of available data
                            # CRITICAL: If read_index >= buffer_size, don't use remainder - wait for new chunks
                            # This ensures both devices wait for new data when they've consumed all available chunks
                            if has_remainder and remainder is not None and current_read_index < current_buffer_size:
                                try:
                                    # Double-check remainder is still valid (defensive programming)
                                    if remainder is None or not hasattr(remainder, '__len__'):
                                        if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                            print(f"  Device {device_num} callback #{callback_num}: ⚠ Remainder became None or invalid!")
                                        remainder_buffers[device_num] = None
                                        chunk = None
                                    else:
                                        remainder_len = len(remainder)
                                        if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS or callback_num % DEBUG_LOG_EVERY_N_CALLBACKS == 0:
                                            print(f"  Device {device_num} callback #{callback_num}: ✓ Processing remainder ({remainder_len} frames, need {frames})...")
                                        
                                        # Use remainder - it can be any size (7168, 6144, 5120, etc.)
                                        if remainder_len >= frames:
                                            # Take first 'frames' samples for this callback
                                            chunk = remainder[:frames].copy()
                                            chunk_from_remainder = True  # Mark that chunk came from remainder
                                            
                                            # Store remaining frames as new remainder (if any left)
                                            remaining_frames = remainder_len - frames
                                            if remaining_frames > 0:
                                                remainder_buffers[device_num] = remainder[frames:].copy()
                                                if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS or callback_num % DEBUG_LOG_EVERY_N_CALLBACKS == 0:
                                                    print(f"  Device {device_num} callback #{callback_num}: ✓ Used {frames} frames from remainder ({remainder_len} frames), stored {remaining_frames} frame remainder")
                                            else:
                                                # No remainder left - clear it
                                                remainder_buffers[device_num] = None
                                                if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS or callback_num % DEBUG_LOG_EVERY_N_CALLBACKS == 0:
                                                    print(f"  Device {device_num} callback #{callback_num}: ✓✓✓ Used remainder ({remainder_len} frames), ✓✓✓ CLEARED!")
                                        else:
                                            # Pad remainder if smaller (shouldn't happen, but handle gracefully)
                                            padding = np.zeros((frames - remainder_len, 2), dtype=np.float32)
                                            chunk = np.concatenate([remainder, padding])
                                            chunk_from_remainder = True
                                            remainder_buffers[device_num] = None
                                            if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                                print(f"  Device {device_num} callback #{callback_num}: ⚠ Remainder was smaller than needed ({remainder_len} < {frames}), padded with zeros")
                                except Exception as e:
                                    print(f"ERROR processing remainder for Device {device_num} (callback #{callback_num}): {e}")
                                    import traceback
                                    traceback.print_exc()
                                    remainder_buffers[device_num] = None  # Clear on error
                                    chunk = None
                            
                            # Process chunk (outside lock to avoid holding it too long)
                            if chunk is None:
                                # No data available yet - outdata already filled with zeros
                                # CRITICAL: Don't return - output zeros to keep stream alive
                                # Returning early can cause the stream to stop
                                if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS or callback_num % DEBUG_LOG_EVERY_N_CALLBACKS_SPARSE == 0:
                                    print(f"  Device {device_num} callback #{callback_num}: No chunk available (has_remainder={has_remainder}, remainder={remainder is not None}) - outputting zeros to keep stream alive")
                                # outdata is already filled with zeros above, just continue
                                return
                            
                            # Ensure chunk is stereo (2 channels) - convert if needed
                            if chunk.shape[1] != 2:
                                if chunk.shape[1] == 1:
                                    # Mono to stereo
                                    chunk = np.column_stack((chunk[:, 0], chunk[:, 0]))
                                elif chunk.shape[1] > 2:
                                    # Multi-channel to stereo (take first 2 channels)
                                    chunk = chunk[:, :2]
                            
                            # Handle chunk size mismatch (only if chunk came from buffer, not remainder)
                            # Input chunks from buffer are variable size (PyAudioWPatch typically 65536 frames), but callback requests CALLBACK_FRAMES
                            # If we used remainder, chunk is already the correct size, so skip this
                            if chunk is not None and not chunk_from_remainder:
                                # We have a new chunk from buffer (32768 frames) - process it
                                chunk_frames = len(chunk)
                                
                                if chunk_frames < frames:
                                    # Chunk is smaller - pad with zeros
                                    padding = np.zeros((frames - chunk_frames, 2), dtype=np.float32)
                                    chunk = np.concatenate([chunk, padding])
                                elif chunk_frames > frames:
                                    # Chunk is larger (could be 2048, 4096, or any size) - split it
                                    # Use first 'frames' samples for this callback
                                    outdata_chunk = chunk[:frames].copy()
                                    # Store remainder for next callback(s)
                                    # Remainder can be any size > 0 (e.g., 3072, 2048, or 1024 frames)
                                    remainder = chunk[frames:].copy()
                                    if len(remainder) > 0:
                                        # Store remainder - it can be any size, will be consumed in subsequent callbacks
                                        remainder_buffers[device_num] = remainder
                                        if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS or callback_num % DEBUG_LOG_EVERY_N_CALLBACKS == 0:
                                            print(f"  Device {device_num} callback #{callback_num}: Split chunk ({chunk_frames} frames) - using {frames} frames, storing {len(remainder)} frame remainder")
                                    else:
                                        remainder_buffers[device_num] = None
                                    chunk = outdata_chunk
                                # If chunk_frames == frames, use as-is (perfect match)
                            else:
                                # No chunk and no remainder - will output silence (already filled with zeros)
                                pass
                            
                            # Process chunk only if we have one
                            if chunk is not None:
                                # Apply volume in real-time
                                if current_volume != 1.0:
                                    chunk = chunk * current_volume
                                
                                # Ensure output matches expected shape (handle mono output devices)
                                output_channels = outdata.shape[1]
                                if output_channels == 1:
                                    # Mono output - mix stereo to mono
                                    chunk = (chunk[:, 0] + chunk[:, 1]) / 2.0
                                    chunk = chunk.reshape((-1, 1))
                                elif output_channels == 2:
                                    # Stereo output - use as-is
                                    chunk = chunk[:, :2]
                                else:
                                    # Multi-channel output - pad or truncate
                                    if chunk.shape[1] < output_channels:
                                        padding = np.zeros((chunk.shape[0], output_channels - chunk.shape[1]), dtype=np.float32)
                                        chunk = np.concatenate([chunk, padding], axis=1)
                                    else:
                                        chunk = chunk[:, :output_channels]
                            
                            # Final shape check and copy - CRITICAL for audio output
                            # Only copy if we have a chunk (otherwise outdata is already zeros)
                            if chunk is not None:
                                # Debug: Log chunk info for first N callbacks
                                if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                    chunk_max = np.abs(chunk).max() if len(chunk) > 0 else 0.0
                                    chunk_mean = np.abs(chunk).mean() if len(chunk) > 0 else 0.0
                                    print(f"  Device {device_num} callback #{callback_num}: About to copy chunk to outdata - chunk.shape={chunk.shape}, outdata.shape={outdata.shape}, max={chunk_max:.4f}, mean={chunk_mean:.4f}")
                                
                                try:
                                    if chunk.shape == outdata.shape:
                                        outdata[:] = chunk
                                        if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                            print(f"  Device {device_num} callback #{callback_num}: ✓✓✓ COPIED chunk to outdata successfully!")
                                    else:
                                        # Reshape chunk to match outdata exactly
                                        if chunk.shape[0] != outdata.shape[0]:
                                            if chunk.shape[0] < outdata.shape[0]:
                                                # Pad with zeros (repeat last sample or use zeros)
                                                padding = np.zeros((outdata.shape[0] - chunk.shape[0], chunk.shape[1]), dtype=np.float32)
                                                chunk = np.concatenate([chunk, padding])
                                            else:
                                                # Truncate
                                                chunk = chunk[:outdata.shape[0]]
                                        
                                        if chunk.shape[1] != outdata.shape[1]:
                                            if chunk.shape[1] == 1 and outdata.shape[1] == 2:
                                                # Mono to stereo
                                                chunk = np.column_stack((chunk[:, 0], chunk[:, 0]))
                                            elif chunk.shape[1] == 2 and outdata.shape[1] == 1:
                                                # Stereo to mono
                                                chunk = (chunk[:, 0] + chunk[:, 1]) / 2.0
                                                chunk = chunk.reshape((-1, 1))
                                            elif chunk.shape[1] > outdata.shape[1]:
                                                # Take first N channels
                                                chunk = chunk[:, :outdata.shape[1]]
                                            else:
                                                # Pad channels
                                                padding = np.zeros((chunk.shape[0], outdata.shape[1] - chunk.shape[1]), dtype=np.float32)
                                                chunk = np.concatenate([chunk, padding], axis=1)
                                        
                                        # Now copy (should match now)
                                        if chunk.shape == outdata.shape:
                                            outdata[:] = chunk
                                        else:
                                            # Last resort: copy what we can
                                            min_frames = min(chunk.shape[0], outdata.shape[0])
                                            min_channels = min(chunk.shape[1], outdata.shape[1])
                                            outdata[:min_frames, :min_channels] = chunk[:min_frames, :min_channels]
                                            # Zero out the rest (already filled with zeros above)
                                except Exception as e:
                                    print(f"ERROR copying chunk to outdata for Device {device_num} (callback #{callback_num}): {e}")
                                    print(f"  chunk.shape={chunk.shape if 'chunk' in locals() else 'N/A'}, outdata.shape={outdata.shape}")
                                    import traceback
                                    traceback.print_exc()
                                    # outdata already filled with zeros above
                            # If chunk is None, outdata is already zeros, so we're done
                            
                            # Debug: Check output level AFTER copying to outdata
                            # Use the actual data that was copied to outdata for accurate level checking
                            try:
                                output_level = np.abs(outdata).max()
                                output_mean = np.abs(outdata).mean()
                                current_time = time.time()
                                
                                # Log first few outputs for debugging
                                if callback_num <= DEBUG_LOG_FIRST_N_CALLBACKS:
                                    print(f"  Device {device_num} output chunk #{callback_num}: outdata_shape={outdata.shape}, max={output_level:.4f}, mean={output_mean:.4f}, volume={current_volume:.2f}")
                                    if output_level > SILENCE_THRESHOLD:
                                        print(f"    ✓✓✓ Device {device_num} HAS AUDIO IN OUTPUT BUFFER! ✓✓✓")
                                
                                if current_time - output_level_timers[device_num] > 2.0:
                                    status = "✓✓✓ AUDIO OUTPUT!" if output_level > SILENCE_THRESHOLD else "✗ No audio output"
                                    remainder_info = ""
                                    rem = remainder_buffers.get(device_num)
                                    if rem is not None:
                                        remainder_info = f", remainder={len(rem)} frames"
                                    
                                    # Get current read_index for debugging
                                    with buffer_lock:
                                        read_idx = device_read_indices.get(device_num, 0)
                                    
                                    print(f"Device {device_num} output (callback #{callback_num}): level={output_level:.4f}, mean={output_mean:.4f}, buffer={buffer_size} chunks, read_index={read_idx}, volume={current_volume:.2f}{remainder_info} - {status}")
                                    if output_level > SILENCE_THRESHOLD:
                                        callbacks_per_sec = callback_num / (current_time - output_level_timers[device_num] + 0.1)
                                        print(f"  ✓✓✓ Device {device_num} IS OUTPUTTING AUDIO! ✓✓✓")
                                        print(f"  ✓ Callbacks running at ~{callbacks_per_sec:.1f}/sec - SUSTAINED OUTPUT!")
                                        print(f"  ✓ Audio data is being written to outdata (max={output_level:.4f}) - audio SHOULD be playing!")
                                        print(f"  ✓✓✓ TROUBLESHOOTING: If you don't hear audio, check:")
                                        print(f"      1. Windows Volume Mixer - ensure this app's volume is up")
                                        print(f"      2. Device volume - ensure device is not muted")
                                        print(f"      3. Device selection - ensure correct device is selected")
                                        print(f"      4. Try a different output device to test")
                                        if read_idx < buffer_size:
                                            print(f"  ✓ Device {device_num} is reading from buffer (read_index={read_idx}/{buffer_size}) - progressing correctly!")
                                        else:
                                            print(f"  ⚠ Device {device_num} read_index={read_idx} >= buffer_size={buffer_size} - may be stuck!")
                                    else:
                                        print(f"  ⚠ Device {device_num} output level is {output_level:.4f} - audio may not be audible")
                                        print(f"  ⚠ Check: 1) Windows volume mixer, 2) Device volume, 3) Device is not muted")
                                        print(f"  ⚠ If volume is up and device is not muted, there may be a driver issue")
                                    output_level_timers[device_num] = current_time
                            except Exception as e:
                                print(f"ERROR in output_callback debug for Device {device_num} (callback #{callback_num}): {e}")
                                # Don't return - let the callback complete
                        
                        return output_callback
                    
                    # Create and start input stream
                    # Try PyAudioWPatch first (best WASAPI loopback support)
                    input_stream = None
                    pyaudio_stream = None
                    pyaudio_instance = None
                    
                    if pyaudiowpatch_available:
                        try:
                            print("Attempting to use PyAudioWPatch for WASAPI loopback...")
                            p = pyaudiowpatch.PyAudio()
                            pyaudio_instance = p
                            using_virtual_cable = False  # Track if we're using a virtual cable (initialize here for scope)
                            
                            # CRITICAL: Search for Virtual Audio Cables FIRST (for raw audio capture)
                            # Only use default loopback if no virtual cables are found
                            try:
                                # First, search for all available loopback devices to find virtual cables
                                device_count = p.get_device_count()
                                wasapi_hostapi_index = p.get_host_api_info_by_type(pyaudiowpatch.paWASAPI)['index']
                                
                                # Get CURRENT default output device name
                                try:
                                    default_output_info = p.get_default_output_device_info()
                                    default_output_name = default_output_info['name']
                                    default_output_index = default_output_info['index']
                                    default_output_name_lower = default_output_name.lower()
                                except:
                                    default_output_name = None
                                    default_output_index = None
                                    default_output_name_lower = ""
                                
                                print(f"\n🔍 SEARCHING FOR VIRTUAL AUDIO CABLES (for raw audio capture)...")
                                if default_output_name:
                                    print(f"  Current default output: {default_output_name} (index: {default_output_index})")
                                
                                # Keywords for detection
                                loopback_keywords = ['loopback', 'stereo mix', 'what u hear', 'wave out']
                                mic_keywords = ['microphone', 'mic', 'input', 'recording']
                                virtual_cable_keywords = [
                                    'vb-audio', 'vb audio', 'cable', 'voicemeeter', 'virtual audio', 'vban',
                                    'virtual cable', 'virtualcable', 'vb cable', 'vb-cable', 'vb cable a',
                                    'vb cable b', 'vb cable c', 'vb cable d', 'vb cable e',
                                    'oculus', 'oculuvad'  # Oculus Virtual Audio Device
                                ]
                                
                                # Search for all loopback devices
                                found_loopback_candidates = []
                                for i in range(device_count):
                                    try:
                                        device_info = p.get_device_info_by_index(i)
                                        device_name = device_info.get('name', '').lower()
                                        device_name_full = device_info.get('name', '')
                                        
                                        if device_info.get('hostApi') == wasapi_hostapi_index:
                                            if device_info.get('maxInputChannels', 0) > 0:
                                                is_mic = any(keyword in device_name for keyword in mic_keywords)
                                                has_loopback_in_name = '[loopback]' in device_name.lower()
                                                is_loopback = has_loopback_in_name or any(keyword in device_name for keyword in loopback_keywords)
                                                
                                                if has_loopback_in_name or (is_loopback and not is_mic):
                                                    is_virtual_cable = any(vc_keyword in device_name for vc_keyword in virtual_cable_keywords)
                                                    matches_default = False
                                                    if default_output_name:
                                                        device_base_name = device_name_full.replace('[Loopback]', '').replace('(Loopback)', '').strip()
                                                        default_base_name = default_output_name.strip()
                                                        if (default_base_name.lower() in device_base_name.lower() or 
                                                            device_base_name.lower() in default_base_name.lower() or
                                                            device_base_name.lower() == default_base_name.lower()):
                                                            matches_default = True
                                                    
                                                    found_loopback_candidates.append((i, device_info, is_virtual_cable, matches_default))
                                    except:
                                        continue
                                
                                # Prioritize: virtual cables that match default FIRST (for raw audio from current output)
                                # Then: regular loopback that matches default (captures current output, not raw)
                                # Then: other virtual cables (may be silent)
                                # Then: other loopback devices
                                virtual_cable_matching = [c for c in found_loopback_candidates if c[2] and c[3]]
                                matching_devices = [c for c in found_loopback_candidates if not c[2] and c[3]]
                                virtual_cable_non_matching = [c for c in found_loopback_candidates if c[2] and not c[3]]
                                non_matching_devices = [c for c in found_loopback_candidates if not c[2] and not c[3]]
                                # NEW PRIORITY: Match default first (captures what's actually playing), then virtual cables
                                candidates_to_try = virtual_cable_matching + matching_devices + virtual_cable_non_matching + non_matching_devices
                                
                                if virtual_cable_matching:
                                    print(f"  🎉 Found {len(virtual_cable_matching)} Virtual Audio Cable(s) matching default - will use for RAW audio!")
                                if matching_devices:
                                    print(f"  ✓ Found {len(matching_devices)} loopback device(s) matching default - will capture current audio")
                                if virtual_cable_non_matching:
                                    print(f"  ⚠ Found {len(virtual_cable_non_matching)} Virtual Audio Cable(s) (not default - may be silent)")
                                
                                # Try devices in priority order: matching virtual cables > matching loopback > non-matching virtual cables > others
                                stream_created = False
                                found_working = False  # Track if we found a working device
                                for i, device_info, is_virtual_cable, matches_default in candidates_to_try:
                                    device_name_full = device_info.get('name', '')
                                    device_default_rate = int(device_info.get('defaultSampleRate', 44100))
                                    
                                    for alt_rate in [device_default_rate, 44100, 48000, 96000, 192000]:
                                        try:
                                            pyaudio_stream = p.open(
                                                format=pyaudiowpatch.paInt16,
                                                channels=2,
                                                rate=alt_rate,
                                                input=True,
                                                input_device_index=i,
                                                frames_per_buffer=1024,
                                                stream_callback=None
                                            )
                                            pyaudio_input_device = i
                                            input_device_name = device_name_full
                                            sample_rate = alt_rate
                                            channels = 2
                                            stream_created = True
                                            found_working = True  # Mark that we found a working device
                                            using_virtual_cable = is_virtual_cable  # Track if we're using virtual cable
                                            
                                            if is_virtual_cable:
                                                print(f"  🎉 SUCCESS! Using Virtual Audio Cable for RAW audio capture!")
                                                print(f"  ✓ Using device's reported rate ({sample_rate} Hz) - skipping measurement for faster startup!")
                                                if not matches_default:
                                                    print(f"\n  ⚠⚠⚠ IMPORTANT: Virtual cable is NOT your default output! ⚠⚠⚠")
                                                    print(f"  ⚠ Current default: {default_output_name if default_output_name else 'Unknown'}")
                                                    print(f"  ⚠ The virtual cable will be SILENT unless you set it as default!")
                                                    print(f"  💡 To get audio:")
                                                    print(f"     1. Right-click speaker icon → Sounds → Playback tab")
                                                    print(f"     2. Find '{input_device_name.replace('[Loopback]', '').strip()}'")
                                                    print(f"     3. Right-click → Set as Default Device")
                                                    print(f"     4. Restart passthrough\n")
                                            print(f"  Device: {input_device_name}, Rate: {sample_rate} Hz")
                                            break
                                        except Exception as stream_error:
                                            # Continue to next rate/device
                                            continue
                                    if stream_created:
                                        break
                                
                                # If no devices worked from our candidates, fall back to default loopback
                                if not stream_created:
                                    print(f"\n⚠ No matching devices found/working, using default WASAPI loopback...")
                                    print(f"  This will capture from your current default output: {default_output_name if default_output_name else 'Unknown'}")
                                    using_virtual_cable = False  # Not using virtual cable
                                    wasapi_loopback = p.get_default_wasapi_loopback()
                                    pyaudio_input_device = wasapi_loopback['index']
                                    input_device_name = wasapi_loopback['name']
                                    sample_rate = int(wasapi_loopback['defaultSampleRate'])
                                    channels = 2
                                    
                                    # Try to open default loopback
                                    for alt_rate in [sample_rate, 44100, 48000, 96000, 192000]:
                                        try:
                                            pyaudio_stream = p.open(
                                                format=pyaudiowpatch.paInt16,
                                                channels=channels,
                                                rate=alt_rate,
                                                input=True,
                                                input_device_index=pyaudio_input_device,
                                                frames_per_buffer=1024,
                                                stream_callback=None
                                            )
                                            sample_rate = alt_rate
                                            stream_created = True
                                            print(f"✓ Using default WASAPI loopback: {input_device_name} at {sample_rate} Hz")
                                            break
                                        except:
                                            continue
                                    
                                    if not stream_created:
                                        raise Exception("Failed to open default WASAPI loopback")
                                    
                                    if virtual_cable_matching:
                                        print(f"  🎉 Found {len(virtual_cable_matching)} Virtual Audio Cable(s) matching default output - PRIORITIZING for raw audio capture!")
                                        print(f"  ✓ These provide raw audio (bypass Windows volume mixer) AND are receiving audio")
                                    if virtual_cable_non_matching:
                                        print(f"  🎉 Found {len(virtual_cable_non_matching)} Virtual Audio Cable(s) - PRIORITIZING for raw audio capture!")
                                        print(f"  ✓ These provide raw audio (bypass Windows volume mixer)")
                                        if not virtual_cable_matching:
                                            print(f"  ⚠ Note: These don't match default output - may be silent unless set as default")
                                            print(f"  💡 TIP: Set the virtual cable as default output for guaranteed raw audio capture")
                                    if matching_devices:
                                        print(f"  Found {len(matching_devices)} loopback device(s) matching current default output")
                                        if not virtual_cable_matching and not virtual_cable_non_matching:
                                            print(f"  Will try these first before falling back to other devices")
                                    if not virtual_cable_matching and not virtual_cable_non_matching and not matching_devices:
                                        print(f"  ⚠ WARNING: No loopback devices found matching current default: {default_output_name}")
                                        print(f"  Will try other available loopback devices, but they may not capture from the default output")
                                        print(f"  💡 TIP: Install VB-Audio Cable for raw audio capture")
                                    
                                    # Try candidates in order
                                    for i, device_info, is_virtual_cable, matches_default in candidates_to_try:
                                        device_name_full = device_info.get('name', '')
                                        device_default_rate = int(device_info.get('defaultSampleRate', 44100))
                                        
                                        # Try to open this device with its default sample rate first
                                        device_worked = False
                                        alternative_rates = [device_default_rate, 44100, 48000, 96000, 192000]
                                        
                                        for try_rate in alternative_rates:
                                            try:
                                                test_stream = p.open(
                                                    format=pyaudiowpatch.paInt16,
                                                    channels=min(2, device_info['maxInputChannels']),
                                                    rate=try_rate,
                                                    input=True,
                                                    input_device_index=i,
                                                    frames_per_buffer=1024,
                                                    stream_callback=None
                                                )
                                                test_stream.close()
                                                # This device works at this rate!
                                                pyaudio_input_device = i
                                                input_device_name = device_name_full
                                                sample_rate = try_rate
                                                # Use 2 channels for stereo output
                                                channels = 2
                                                print(f"Working loopback device info:")
                                                print(f"  Name: {input_device_name}")
                                                print(f"  Index: {i}")
                                                print(f"  Sample rate: {sample_rate} Hz")
                                                print(f"  Max input channels: {device_info['maxInputChannels']}")
                                                print(f"  Using: {channels} channels (stereo)")
                                                if is_virtual_cable:
                                                    print(f"  🎉 VIRTUAL AUDIO CABLE - RAW AUDIO CAPTURE! 🎉")
                                                    print(f"  ✓ Captures raw audio (bypasses Windows volume mixer)")
                                                    print(f"  ✓ Audio captured regardless of Windows volume level")
                                                    if matches_default:
                                                        print(f"  ✓ This matches your CURRENT default output - perfect setup!")
                                                        print(f"  ✓ Capturing from: {default_output_name}")
                                                    else:
                                                        print(f"  ⚠ Note: Current default is: {default_output_name if default_output_name else 'Unknown'}")
                                                        print(f"  ⚠ For best results, set this virtual cable as your default output")
                                                elif matches_default:
                                                    print(f"  ✓ This matches your CURRENT default output device - will capture all system audio!")
                                                    print(f"  ✓ Capturing from: {default_output_name}")
                                                    print(f"  ⚠ Note: Capture is affected by Windows volume (not raw audio)")
                                                    print(f"  💡 TIP: Use a Virtual Audio Cable for raw audio capture")
                                                else:
                                                    print(f"  ⚠⚠⚠ WARNING: This is NOT your current default output! ⚠⚠⚠")
                                                    print(f"  ⚠ Current default is: {default_output_name if default_output_name else 'Unknown'}")
                                                    print(f"  ⚠ This device may not capture audio from the current default output")
                                                    print(f"  ⚠ To capture from the current default, set it as default in Windows and restart passthrough")
                                                
                                                pyaudio_stream = p.open(
                                                    format=pyaudiowpatch.paInt16,
                                                    channels=channels,
                                                    rate=sample_rate,
                                                    input=True,
                                                    input_device_index=pyaudio_input_device,
                                                    frames_per_buffer=1024,
                                                    stream_callback=None
                                                )
                                                # CRITICAL: Get the ACTUAL sample rate from the stream
                                                actual_sample_rate = sample_rate
                                                try:
                                                    device_info_check = p.get_device_info_by_index(i)
                                                    actual_sample_rate = int(device_info_check.get('defaultSampleRate', sample_rate))
                                                except:
                                                    pass
                                                if actual_sample_rate != sample_rate:
                                                    print(f"  ⚠ Stream created at {sample_rate} Hz but actual rate is {actual_sample_rate} Hz")
                                                    sample_rate = actual_sample_rate
                                                print(f"✓ Found working WASAPI loopback: {input_device_name} (index: {i})")
                                                found_working = True
                                                device_worked = True
                                                break
                                            except Exception as test_error:
                                                # Try next sample rate
                                                continue
                                        
                                        if device_worked:
                                            break
                                        
                                        # If this was a matching device and it failed, warn the user
                                        if matches_default:
                                            print(f"  ⚠ Could not open loopback for current default: {device_name_full}")
                                            print(f"  ⚠ Tried sample rates: {alternative_rates}")
                                            print(f"  ⚠ Will try other loopback devices, but they may not match your default output")
                                    
                                    # Only check found_working if we went through the old code path
                                    # (new path sets found_working directly when stream is created)
                                    if not stream_created and not found_working:
                                        print("\n⚠ Could not find a working WASAPI loopback device")
                                        print("  Note: WASAPI loopback captures from the Windows default output device")
                                        print("  To capture audio:")
                                        print("    1. Set the device you want to capture FROM as the default output in Windows")
                                        print("    2. Make sure that device supports WASAPI loopback")
                                        print("    3. Restart passthrough after changing the default device")
                                        raise Exception("Could not find a working WASAPI loopback device")
                                    
                                    # Final check: if we're using a non-matching device, warn prominently
                                    # Only do this check if we successfully created a stream
                                    if (found_working or stream_created) and default_output_name and 'input_device_name' in locals():
                                        # Check if the device we're using is a virtual cable or matches the default
                                        using_matching_device = False
                                        is_using_virtual_cable = False
                                        if input_device_name:
                                            input_device_name_lower = input_device_name.lower()
                                            is_using_virtual_cable = any(vc_keyword in input_device_name_lower for vc_keyword in virtual_cable_keywords)
                                            
                                            device_base = input_device_name.replace('[Loopback]', '').replace('(Loopback)', '').strip()
                                            default_base = default_output_name.strip()
                                            if (default_base.lower() in device_base.lower() or 
                                                device_base.lower() in default_base.lower() or
                                                device_base.lower() == default_base.lower()):
                                                using_matching_device = True
                                        
                                        if is_using_virtual_cable and not using_matching_device:
                                            print(f"\n{'='*60}")
                                            print(f"💡 VIRTUAL AUDIO CABLE DETECTED - Setup Recommendation")
                                            print(f"{'='*60}")
                                            print(f"  Current Windows default output: {default_output_name}")
                                            print(f"  Using Virtual Audio Cable: {input_device_name}")
                                            print(f"  ✓ Virtual cable provides RAW audio (bypasses Windows volume mixer)")
                                            print(f"  💡 For best results, set the virtual cable as your default output:")
                                            print(f"     1. Right-click speaker icon → Sounds → Playback tab")
                                            print(f"     2. Find '{input_device_name.replace('[Loopback]', '').strip()}'")
                                            print(f"     3. Right-click → Set as Default Device")
                                            print(f"     4. Restart passthrough")
                                            print(f"{'='*60}\n")
                                        elif not using_matching_device:
                                            print(f"\n{'='*60}")
                                            print(f"⚠⚠⚠ WARNING: Using non-default loopback device! ⚠⚠⚠")
                                            print(f"{'='*60}")
                                            print(f"  Current Windows default output: {default_output_name}")
                                            print(f"  Using loopback device: {input_device_name}")
                                            print(f"  ⚠ This loopback may NOT capture audio from the current default output!")
                                            print(f"  ⚠ To capture from '{default_output_name}':")
                                            print(f"     1. Set '{default_output_name}' as the default output in Windows")
                                            print(f"     2. Restart passthrough")
                                            print(f"  💡 TIP: Use a Virtual Audio Cable for raw audio capture!")
                                            print(f"{'='*60}\n")
                                
                            except Exception as e:
                                print(f"PyAudioWPatch WASAPI loopback failed: {e}")
                                import traceback
                                traceback.print_exc()
                                if p:
                                    p.terminate()
                                pyaudio_instance = None
                                pyaudiowpatch_available = False
                        except Exception as e:
                            print(f"PyAudioWPatch initialization failed: {e}")
                            import traceback
                            traceback.print_exc()
                            pyaudiowpatch_available = False
                    
                    # Fallback to sounddevice if PyAudioWPatch didn't work
                    if not pyaudiowpatch_available or pyaudio_stream is None:
                        print("Using sounddevice for audio capture...")
                        wasapi_hostapi = None
                    
                    # Find WASAPI host API
                    for hostapi_idx, hostapi_info in enumerate(sd.query_hostapis()):
                        if 'wasapi' in hostapi_info.get('name', '').lower():
                            wasapi_hostapi = hostapi_idx
                            break
                    
                    if wasapi_hostapi is not None and default_output is not None:
                        # Get the WASAPI version of the default output device
                        default_output_info = sd.query_devices(default_output)
                        default_output_name = default_output_info['name']
                        
                        # Find WASAPI device index for the default output
                        wasapi_device_idx = None
                        for i, device in enumerate(devices):
                            if device.get('hostapi') == wasapi_hostapi:
                                device_info = sd.query_devices(i)
                                if device_info['name'] == default_output_name and device_info.get('max_output_channels', 0) > 0:
                                    wasapi_device_idx = i
                                    print(f"Found WASAPI output device: {device_info['name']} (WASAPI index: {i})")
                                    break
                        
                        if wasapi_device_idx is not None:
                            # Use WASAPI loopback: access output device as input (loopback mode)
                            # In sounddevice, this is done by using the device tuple (hostapi, device_index)
                            # First, check what channels the device supports
                            try:
                                wasapi_device_info = sd.query_devices(wasapi_device_idx)
                                # For loopback, we need to check input channels available
                                # WASAPI loopback typically supports the same channels as output
                                loopback_channels = min(2, wasapi_device_info.get('max_output_channels', 2))
                                print(f"WASAPI device supports {loopback_channels} channels for loopback")
                                
                                # Method 1: Use tuple format (hostapi, device_index) for WASAPI loopback
                                try:
                                    input_stream = sd.InputStream(
                                        device=(wasapi_hostapi, wasapi_device_idx),
                                        channels=loopback_channels,
                                        samplerate=sample_rate,
                                        callback=input_callback,
                                        dtype=np.float32,
                                        blocksize=1024
                                    )
                                    channels = loopback_channels  # Update channels to match
                                    print(f"✓ Created WASAPI loopback stream using tuple format ({loopback_channels} channels)")
                                except Exception as e1:
                                    print(f"WASAPI loopback tuple method failed: {e1}")
                                    # Method 2: Try setting hostapi as default and use device index
                                    try:
                                        old_hostapi = sd.default.hostapi
                                        sd.default.hostapi = wasapi_hostapi
                                        input_stream = sd.InputStream(
                                            device=wasapi_device_idx,
                                            channels=loopback_channels,
                                            samplerate=sample_rate,
                                            callback=input_callback,
                                            dtype=np.float32,
                                            blocksize=1024
                                        )
                                        channels = loopback_channels  # Update channels to match
                                        sd.default.hostapi = old_hostapi
                                        print(f"✓ Created WASAPI loopback stream using hostapi method ({loopback_channels} channels)")
                                    except Exception as e2:
                                        print(f"WASAPI loopback hostapi method also failed: {e2}")
                                        sd.default.hostapi = old_hostapi
                                        input_stream = None
                            except Exception as e0:
                                print(f"Error checking WASAPI device info: {e0}")
                                input_stream = None
                    
                    # If WASAPI loopback didn't work, try loopback devices (Stereo Mix, Internal AUX, etc.)
                    # BUT ONLY if PyAudioWPatch also failed (don't overwrite successful PyAudioWPatch stream)
                    if input_stream is None and pyaudio_stream is None:
                        print("WASAPI loopback failed, trying loopback devices (Stereo Mix, Internal AUX, etc.)...")
                        if loopback_device is not None:
                            loopback_device_info = sd.query_devices(loopback_device)
                            loopback_device_name = loopback_device_info['name']
                            loopback_device_name_lower = loopback_device_name.lower()
                            
                            # Don't use if it's clearly a microphone
                            if 'microphone' not in loopback_device_name_lower and 'mic' not in loopback_device_name_lower:
                                # Get the actual channel count for this device
                                device_channels = min(2, loopback_device_info.get('max_input_channels', 2))
                                device_sample_rate = int(loopback_device_info.get('default_samplerate', sample_rate))
                                
                                print(f"Trying loopback device: {loopback_device_name}")
                                print(f"  Device supports {device_channels} channels, {device_sample_rate} Hz")
                                
                                # Try different channel configurations
                                # Some devices work better with specific channel counts
                                channel_configs = []
                                
                                # Add device's max channels if > 0
                                max_channels = loopback_device_info.get('max_input_channels', 0)
                                if max_channels > 0:
                                    channel_configs.append(max_channels)
                                
                                # Add common configurations
                                if max_channels >= 2:
                                    channel_configs.append(2)  # Stereo
                                if max_channels >= 1:
                                    channel_configs.append(1)  # Mono
                                
                                # Remove duplicates and sort
                                channel_configs = sorted(list(set(channel_configs)), reverse=True)
                                
                                input_stream = None
                                for try_channels in channel_configs:
                                    try:
                                        print(f"  Trying {try_channels} channel(s)...")
                                        input_stream = sd.InputStream(
                                            device=loopback_device,
                                            channels=try_channels,
                                            samplerate=device_sample_rate,
                                            callback=input_callback,
                                            dtype=np.float32,
                                            blocksize=1024
                                        )
                                        channels = try_channels
                                        sample_rate = device_sample_rate
                                        print(f"✓ Created input stream with {loopback_device_name} ({try_channels} channels, {device_sample_rate} Hz)")
                                        break
                                    except Exception as e:
                                        print(f"  Failed with {try_channels} channel(s): {e}")
                                        input_stream = None
                                        continue
                                
                                # If mono worked, we'll need to convert to stereo for output
                                if input_stream is not None and channels == 1:
                                    print("  Note: Input is mono, will convert to stereo for output")
                    
                    # If we still don't have a stream, raise an error with clear instructions
                    # Check both PyAudioWPatch stream (pyaudio_stream) and sounddevice stream (input_stream)
                    if input_stream is None and pyaudio_stream is None:
                        # Provide better error message based on what we tried
                        if using_virtual_cable:
                            error_msg = (
                                "Could not create audio capture stream from Virtual Audio Cable.\n\n"
                                "The virtual cable was detected but the stream could not be opened.\n\n"
                                "Troubleshooting:\n"
                                "1. Make sure the virtual cable is not being used by another application\n"
                                "2. Try restarting the application\n"
                                "3. If using Oculus Virtual Audio Device, make sure Oculus software is running\n"
                                "4. Consider installing VB-Audio Cable as an alternative\n\n"
                                "Alternative: Use WASAPI loopback (set your desired output as Windows default)"
                            )
                        else:
                            error_msg = (
                                "Could not create audio capture stream.\n\n"
                                "REQUIRED: Enable Stereo Mix in Windows:\n"
                                "1. Right-click speaker icon → Sounds\n"
                                "2. Go to 'Recording' tab\n"
                                "3. Right-click empty area → 'Show Disabled Devices'\n"
                                "4. Find 'Stereo Mix' → Right-click → 'Enable'\n"
                                "5. Right-click 'Stereo Mix' → 'Set as Default Device'\n"
                                "6. Restart this application\n\n"
                                "Alternative: Install VB-Audio Cable or VoiceMeeter\n"
                                "for virtual audio routing."
                            )
                        raise Exception(error_msg)
                    
                    # Create output streams for each device
                    # Always use 2 channels (stereo) for output, regardless of input channels
                    # IMPORTANT: Use the same sample rate as the input to avoid resampling issues
                    output_channels = 2
                    output_streams = []
                    print(f"\n=== Creating output streams for {len(devices_to_use)} device(s) ===")
                    print(f"  Current sample_rate variable: {sample_rate} Hz")
                    
                    # CRITICAL: Ensure sample_rate is correctly set based on the actual input stream
                    # The sample_rate variable may have been updated by the capture thread's measurement
                    if pyaudio_stream is not None:
                        print(f"\n{'='*60}")
                        print(f"✓ AUDIO CAPTURE CONFIGURED")
                        print(f"{'='*60}")
                        print(f"  Capturing from: {input_device_name if 'input_device_name' in locals() else 'WASAPI Loopback'}")
                        print(f"  Sample rate: {sample_rate} Hz")
                        print(f"  Channels: 2 (stereo)")
                        print(f"  ⚠ NOTE: Actual rate will be measured from chunk timing - may differ from device default")
                        print(f"  ⚠ IMPORTANT: This captures from the Windows DEFAULT output device")
                        print(f"     If you want to capture from a different device:")
                        print(f"     1. Set that device as the default output in Windows Sound Settings")
                        print(f"     2. Restart passthrough to capture from the new device")
                        print(f"\n  📌 ABOUT RAW AUDIO CAPTURE:")
                        print(f"     WASAPI loopback captures audio AFTER the Windows volume mixer.")
                        print(f"     This means low/muted volume = low/muted capture.")
                        print(f"     To capture 'raw' audio (before volume mixer):")
                        print(f"     → Use a Virtual Audio Cable (VB-Audio Cable, VoiceMeeter, etc.)")
                        print(f"     → Set the virtual cable as your default output")
                        print(f"     → Capture from the virtual cable's input")
                        print(f"     → This bypasses Windows volume mixing")
                        print(f"{'='*60}\n")
                    else:
                        # Using sounddevice input - sample_rate should already be set correctly
                        print(f"  Using sounddevice input at {sample_rate} Hz")
                    
                    print(f"  Output will use {output_channels} channels (stereo) and sample rate: {sample_rate} Hz")
                    print(f"  (Matching input sample rate to avoid resampling)")
                    
                    for device_idx, device_num, volume in devices_to_use:
                        try:
                            device_info = sd.query_devices(device_idx)
                            device_name = device_info['name']
                            device_max_channels = device_info.get('max_output_channels', 2)
                            device_default_rate = int(device_info.get('default_samplerate', sample_rate))
                            
                            # Use the minimum of what device supports and what we want (stereo)
                            device_channels = min(output_channels, device_max_channels)
                            
                            # Try to use input sample rate, but fall back to device default if needed
                            output_sample_rate = sample_rate
                            if device_default_rate != sample_rate:
                                print(f"  Note: Device default rate is {device_default_rate} Hz, but using {sample_rate} Hz to match input")
                            
                            print(f"Creating output stream for Device {device_num}:")
                            print(f"  Name: {device_name}")
                            print(f"  Index: {device_idx}")
                            print(f"  Sample rate: {output_sample_rate} Hz (matching input)")
                            print(f"  Channels: {device_channels} (device supports {device_max_channels})")
                            
                            output_callback = make_output_callback(device_num)
                            
                            output_stream = sd.OutputStream(
                                device=device_idx,
                                channels=device_channels,
                                samplerate=output_sample_rate,
                                callback=output_callback,
                                dtype=np.float32,
                                blocksize=1024
                            )
                            output_streams.append((output_stream, device_name, device_num))
                            print(f"  ✓ Output stream created successfully\n")
                        except Exception as e:
                            print(f"  ✗ ERROR: Failed to create output stream: {e}")
                            import traceback
                            traceback.print_exc()
                            # Continue with other devices
                    
                    if not output_streams:
                        raise Exception("Failed to create any output streams. Check device selection.")
                    
                    # CRITICAL: Measure latency for each device SYNCHRONOUSLY before calculating offsets
                    # This ensures accurate synchronization - both devices must be measured before offsets are calculated
                    print(f"\n=== Measuring device latencies for synchronization (CRITICAL: Must complete before passthrough) ===")
                    device_latencies = {}
                    device_read_offsets = {}  # device_num -> read_index offset
                    # device_drift_adjustments removed - runtime corrections cause stuttering
                    
                    # Priority: 1) Use GUI-measured latencies (already accurate), 2) Measure synchronously, 3) Default
                    for stream, device_name, device_num in output_streams:
                        latency_found = False
                        device_idx = None
                        
                        # Find device index
                        for dev_idx, dev_num, _ in devices_to_use:
                            if dev_num == device_num:
                                device_idx = dev_idx
                                break
                        
                        # FIRST: Try to use GUI-measured latency (already accurate, includes Bluetooth)
                        if device_num == 1 and hasattr(self, 'device1_measured_latency') and self.device1_measured_latency > 0:
                            device_latencies[device_num] = self.device1_measured_latency / 1000.0
                            print(f"Device {device_num} ({device_name}): Using GUI-measured latency {self.device1_measured_latency:.1f}ms")
                            latency_found = True
                        elif device_num == 2 and hasattr(self, 'device2_measured_latency') and self.device2_measured_latency > 0:
                            device_latencies[device_num] = self.device2_measured_latency / 1000.0
                            print(f"Device {device_num} ({device_name}): Using GUI-measured latency {self.device2_measured_latency:.1f}ms")
                            latency_found = True
                        elif device_num > 2:
                            # Check dynamic devices
                            for w in self.device_widgets:
                                if w['device_num'] == device_num:
                                    meas = w.get('measured_latency', 0.0)
                                    if meas > 0:
                                        device_latencies[device_num] = meas / 1000.0
                                        print(f"Device {device_num} ({device_name}): Using GUI-measured latency {meas:.1f}ms")
                                        latency_found = True
                                    break
                        
                        # SECOND: If no GUI measurement, try to measure synchronously
                        # CRITICAL: This MUST complete before sync calculation - no async operations
                        if not latency_found and device_idx is not None:
                            try:
                                print(f"Device {device_num} ({device_name}): Measuring latency synchronously (REQUIRED for sync - this may take a few seconds)...")
                                
                                # Try player method first (if available)
                                latency = None
                                if hasattr(self, 'player') and self.player is not None:
                                    try:
                                        # Measure latency using the player's method (synchronous, blocking)
                                        # This includes Bluetooth compensation automatically
                                        # CRITICAL: This is a blocking call - it will not return until measurement is complete
                                        latency = self.player._get_device_latency(
                                            device_idx, device_name, sample_rate, measure=True
                                        )
                                        if latency and latency > 0:
                                            print(f"  ✓ Player method succeeded: {latency*1000:.1f}ms")
                                    except Exception as e:
                                        print(f"  ⚠ Player method failed: {e}, trying LatencyManager directly...")
                                
                                # Fallback: Use LatencyManager directly if player method failed or player is None
                                if latency is None or latency <= 0:
                                    try:
                                        from bluetoothstreamer.core.latency_manager import LatencyManager
                                        latency_manager = LatencyManager()
                                        # Measure latency directly (synchronous, blocking)
                                        print(f"  ⚠ Using LatencyManager directly (player unavailable or failed)...")
                                        latency = latency_manager.measure_device_latency(
                                            device_idx, device_name, sample_rate, num_measurements=3
                                        )
                                        # Add Bluetooth transmission latency if Bluetooth device
                                        if DeviceManager and DeviceManager.is_bluetooth_device(device_name):
                                            bluetooth_transmission_latency = 0.075  # 75ms
                                            latency += bluetooth_transmission_latency
                                            print(f"  ✓ Added Bluetooth transmission latency: +{bluetooth_transmission_latency*1000:.1f}ms")
                                        if latency and latency > 0:
                                            print(f"  ✓ LatencyManager method succeeded: {latency*1000:.1f}ms")
                                    except Exception as e:
                                        print(f"  ⚠ LatencyManager method also failed: {e}")
                                        import traceback
                                        traceback.print_exc()
                                
                                # CRITICAL: Verify measurement succeeded before using it
                                if latency and latency > 0:
                                    device_latencies[device_num] = latency
                                    latency_ms = latency * 1000.0
                                    print(f"Device {device_num} ({device_name}): {latency_ms:.1f}ms latency (measured synchronously)")
                                    
                                    # Update GUI stored latency for future use
                                    if device_num == 1:
                                        self.device1_measured_latency = latency_ms
                                    elif device_num == 2:
                                        self.device2_measured_latency = latency_ms
                                    
                                    latency_found = True
                                else:
                                    print(f"WARNING: Device {device_num} latency measurement returned 0 or failed - measurement may have failed")
                                    print(f"  ⚠⚠⚠ CRITICAL: Sync will be inaccurate without proper latency measurement!")
                            except Exception as e:
                                print(f"ERROR: Could not measure latency for Device {device_num}: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # LAST RESORT: use default latency estimate
                        if not latency_found:
                            device_latencies[device_num] = 0.1  # 100ms default
                            print(f"WARNING: Device {device_num} ({device_name}): Using default 100ms latency (no measurement available)")
                    
                    # Calculate read_index offsets based on latency differences
                    if device_latencies:
                        max_latency = max(device_latencies.values())
                        # CRITICAL: Chunks in buffer are 65536 frames each (not 1024)
                        # 1024 is the callback size, but chunks stored in buffer are 65536 frames
                        frames_per_chunk = 65536  # Actual chunk size in buffer
                        chunk_duration_seconds = frames_per_chunk / sample_rate
                        chunks_per_second = 1.0 / chunk_duration_seconds
                        
                        print(f"\n=== Calculating read_index offsets ===")
                        print(f"Max latency: {max_latency*1000:.1f}ms")
                        print(f"Chunks per second: {chunks_per_second:.1f} (chunk size: {frames_per_chunk} frames = {chunk_duration_seconds*1000:.1f}ms)")
                        
                        # CRITICAL SYNCHRONIZATION LOGIC:
                        # Device with HIGHER latency must start reading EARLIER (from position 0 immediately)
                        # Device with LOWER latency must WAIT (negative read_index, then start at position 0)
                        # This ensures both devices output audio at the same time despite different latencies
                        for device_num, latency in device_latencies.items():
                            # Calculate latency difference from max latency
                            latency_diff = max_latency - latency
                            
                            if latency_diff == 0:
                                # This is the device with max latency - starts immediately
                                wait_chunks = 0
                            else:
                                # Lower latency device - must wait to synchronize
                                # Convert latency difference to chunks
                                # Use precise calculation: latency_diff in seconds * chunks_per_second
                                wait_chunks_float = latency_diff * chunks_per_second
                                
                                # CRITICAL: For any latency difference > 10ms, we MUST apply delay
                                # Even small differences will cause audible desync
                                if wait_chunks_float < 0.01:
                                    # Extremely small difference (<0.01 chunks = ~14ms) - don't wait
                                    wait_chunks = 0
                                else:
                                    # Any meaningful difference - always wait at least 1 chunk OR use time-based delay
                                    # For differences < 500ms, we'll use time-based delay (handled later)
                                    # For larger differences, use chunk-based waiting
                                    wait_chunks = max(1, int(round(wait_chunks_float)))
                            
                            device_read_offsets[device_num] = wait_chunks
                            wait_time_ms = wait_chunks * chunk_duration_seconds * 1000.0
                            print(f"Device {device_num}: latency={latency*1000:.1f}ms, latency_diff={latency_diff*1000:.1f}ms, wait_chunks={wait_chunks} (wait_time={wait_time_ms:.1f}ms)")
                        
                        # Initialize read indices and start times for precise synchronization
                        # For small latency differences, use time-based delay instead of chunk-based
                        # device_start_times is already defined in outer scope - just populate it
                        passthrough_start_time = None  # Will be set when streams start
                        
                        # Get device names for Bluetooth detection
                        device_names_map = {}
                        for stream, device_name, device_num in output_streams:
                            device_names_map[device_num] = device_name
                        
                        for device_num, wait_chunks in device_read_offsets.items():
                            latency_diff = (max_latency - device_latencies[device_num]) * 1000.0  # Convert to ms
                            
                            # Check if this is a Bluetooth device
                            device_name = device_names_map.get(device_num, "")
                            is_bluetooth = False
                            if DeviceManager:
                                is_bluetooth = DeviceManager.is_bluetooth_device(device_name)
                            
                            if wait_chunks == 0:
                                # Highest latency device - but if it's Bluetooth, add adaptive safety delay
                                # Bluetooth devices can start playing before their measured latency due to buffering
                                # The safety delay should be proportional to the device's latency to work across different systems
                                if is_bluetooth:
                                    # Calculate adaptive safety delay: 3-4% of measured latency, with min 5ms and max 25ms
                                    # Reduced from 4% to 3.5% and max from 30ms to 25ms for better sync accuracy
                                    # This scales with the device's actual latency characteristics
                                    device_latency_ms = device_latencies[device_num] * 1000.0
                                    bluetooth_safety_delay_percent = 0.035  # 3.5% of measured latency (reduced from 4% for better accuracy)
                                    bluetooth_safety_delay_ms = max(5.0, min(25.0, device_latency_ms * bluetooth_safety_delay_percent))  # Reduced max from 30ms to 25ms
                                    device_read_indices[device_num] = 0
                                    device_start_times[device_num] = bluetooth_safety_delay_ms / 1000.0  # Store delay in seconds
                                    print(f"Device {device_num} initial read_index: 0 (Bluetooth device - adding {bluetooth_safety_delay_ms:.1f}ms adaptive safety delay ({bluetooth_safety_delay_percent*100:.1f}% of {device_latency_ms:.1f}ms latency) to prevent early start)")
                                else:
                                    # Non-Bluetooth highest latency device - starts immediately
                                    device_read_indices[device_num] = 0
                                    device_start_times[device_num] = None  # Start immediately
                                    print(f"Device {device_num} initial read_index: 0 (starts immediately - highest latency device)")
                            elif latency_diff < 500.0 and latency_diff >= 5.0:
                                # Small latency difference (5-500ms) - use time-based delay for precision
                                # Add adaptive buffer to lower latency device based on latency difference
                                # Reduced buffer to improve sync accuracy - buffer scales with latency difference: 2-3% of difference, with min 2ms and max 12ms
                                buffer_percent = 0.025  # 2.5% of latency difference (reduced from 3% for better accuracy)
                                buffer_ms = max(2.0, min(12.0, latency_diff * buffer_percent))  # Reduced max from 15ms to 12ms
                                total_delay_ms = latency_diff + buffer_ms
                                device_read_indices[device_num] = 0  # Start reading from position 0
                                device_start_times[device_num] = total_delay_ms / 1000.0  # Store delay in seconds (will be added to stream start time)
                                print(f"Device {device_num} initial read_index: 0 (will delay output by {total_delay_ms:.2f}ms using time-based delay: {latency_diff:.2f}ms base + {buffer_ms:.1f}ms adaptive buffer ({buffer_percent*100:.1f}% of difference))")
                            elif latency_diff < 5.0:
                                # Very small latency difference (<5ms) - start immediately (negligible)
                                device_read_indices[device_num] = 0
                                device_start_times[device_num] = None
                                print(f"Device {device_num} initial read_index: 0 (latency diff {latency_diff:.2f}ms < 5ms - negligible, starting immediately)")
                            else:
                                # Larger latency difference - use chunk-based waiting
                                device_read_indices[device_num] = -wait_chunks  # Negative means "wait for buffer"
                                device_start_times[device_num] = None  # Will start when buffer is ready
                                print(f"Device {device_num} initial read_index: -{wait_chunks} (will wait {wait_chunks} chunks, then start at position 0)")
                    
                    # Multi-Bluetooth Sync: Add devices to sync coordinator
                    if MULTI_BLUETOOTH_SYNC_AVAILABLE and self.sync_coordinator:
                        print("\n=== Initializing Multi-Bluetooth Sync Components ===")
                        for device_idx, device_num, _ in devices_to_use:
                            device_info = sd.query_devices(device_idx)
                            device_name = device_info['name']
                            
                            # Detect if Bluetooth - STRICT detection to avoid false positives with wired headphones
                            # Use DeviceManager's static method (doesn't require self.player)
                            if DeviceManager:
                                is_bluetooth = DeviceManager.is_bluetooth_device(device_name)
                            else:
                                # Fallback: use inline detection if DeviceManager not available
                                device_name_lower = device_name.lower()
                                bluetooth_indicators = [
                                    'bluetooth', ' bt', 'bt ', 'bth', 'hands-free', 'a2dp', 'bthhfenum'
                                ]
                                bluetooth_only_brands = ['airpods', 'galaxy buds', 'pixel buds', 'tws']
                                is_bluetooth = (
                                    any(indicator in device_name_lower for indicator in bluetooth_indicators) or
                                    any(brand in device_name_lower for brand in bluetooth_only_brands) or
                                    '@system32\\drivers\\bthhfenum' in device_name_lower
                                )
                            
                            # Get initial latency - use GUI-measured latency (most accurate)
                            # The codec detector might give different values, but we want the actual measured latency
                            if device_num == 1 and hasattr(self, 'device1_measured_latency') and self.device1_measured_latency > 0:
                                initial_latency_ms = self.device1_measured_latency
                            elif device_num == 2 and hasattr(self, 'device2_measured_latency') and self.device2_measured_latency > 0:
                                initial_latency_ms = self.device2_measured_latency
                            else:
                                initial_latency_ms = device_latencies.get(device_num, 0.1) * 1000.0
                            
                            # Log codec detection but don't override measured latency
                            if is_bluetooth and self.codec_detector:
                                codec_latency = self.codec_detector.get_codec_latency(device_idx, device_name)
                                print(f"  Device {device_num} ({device_name}): Detected codec latency {codec_latency:.1f}ms (using measured: {initial_latency_ms:.1f}ms)")
                            
                            # Add to sync coordinator
                            self.sync_coordinator.add_device(device_idx, device_name, is_bluetooth, initial_latency_ms)
                            
                            # Add to jitter measurer
                            if self.jitter_measurer:
                                expected_interval = 1024.0 / sample_rate  # Callback interval
                                self.jitter_measurer.add_device(device_idx, device_name, expected_interval)
                            
                            # Add to clock synchronizer
                            if self.clock_synchronizer:
                                self.clock_synchronizer.add_device(device_idx, device_name)
                            
                            # Add to buffer manager
                            if self.buffer_manager:
                                # Get recommended buffer size from jitter measurer if available
                                if self.jitter_measurer:
                                    recommended = self.jitter_measurer.get_recommended_buffer(device_idx)
                                else:
                                    recommended = 300.0  # Default
                                self.buffer_manager.add_device(device_idx, recommended)
                            
                            # Add to signal monitor
                            if self.signal_monitor:
                                self.signal_monitor.add_device(device_idx, device_name)
                            
                            print(f"  ✓ Device {device_num} added to sync system")
                        
                        # Set reference device (highest latency)
                        if self.clock_synchronizer and self.reference_device:
                            ref_idx = self.device1_index if self.reference_device == 1 else self.device2_index
                            if ref_idx:
                                self.clock_synchronizer.set_reference_device(ref_idx)
                        
                        # Start coordination
                        # DISABLED: Real-time sync coordination causes stuttering during playback
                        # We rely on initial synchronization before playback starts instead
                        # All sync adjustments happen BEFORE audio starts playing
                        # self.sync_coordinator.start_coordinating()
                        # if self.clock_synchronizer:
                        #     self.clock_synchronizer.start_syncing()
                        # if self.signal_monitor:
                        #     self.signal_monitor.start_monitoring()
                        
                        print("  ⚠ Real-time sync coordination DISABLED (prevents stuttering - using initial sync only)")
                        print("  ✓ Multi-Bluetooth sync components initialized (monitoring only, no corrections)\n")
                    
                    # Store all streams
                    if pyaudio_stream is not None:
                        # Using PyAudioWPatch - store PyAudio object
                        self.passthrough_streams = [pyaudio_stream] + [stream for stream, _, _ in output_streams]
                        self.pyaudio_instance = pyaudio_instance  # Store PyAudio instance for cleanup
                        self.pyaudio_capture_stream = pyaudio_stream  # Store reference for quick stopping
                    else:
                        # Using sounddevice
                        self.passthrough_streams = [input_stream] + [stream for stream, _, _ in output_streams]
                        self.pyaudio_instance = None
                    
                    # Start all streams
                    print("=== Starting audio pass-through streams ===")
                    print(f"Input device: {input_device_name}")
                    print(f"Output devices: {len(output_streams)} device(s)")
                    for stream, device_name, device_num in output_streams:
                        print(f"  Device {device_num}: {device_name}")
                        # CRITICAL: Verify actual sample rate AFTER stream is created (before starting)
                        try:
                            actual_rate = stream.samplerate
                            if actual_rate != sample_rate:
                                print(f"  ⚠⚠⚠ CRITICAL WARNING: Device {device_num} ({device_name})")
                                print(f"    Requested {sample_rate} Hz but stream is using {actual_rate} Hz!")
                                speed_factor = actual_rate / sample_rate
                                print(f"    ⚠⚠⚠ Audio will play at {speed_factor:.3f}x speed ({'SLOWED DOWN' if speed_factor < 1.0 else 'SPED UP'})!")
                                print(f"    ⚠⚠⚠ This is a device driver limitation - device doesn't support {sample_rate} Hz")
                                print(f"    ⚠⚠⚠ SOLUTION: Use a different output device that supports {sample_rate} Hz")
                            else:
                                print(f"  ✓ Device {device_num} verified: Using correct sample rate ({actual_rate} Hz)")
                        except Exception as e:
                            print(f"  ⚠ Could not verify sample rate for Device {device_num}: {e}")
                            print(f"    Assuming stream is using requested rate: {sample_rate} Hz")
                    
                    # Start input capture
                    if pyaudio_stream is not None:
                        # Start PyAudio stream
                        pyaudio_stream.start_stream()
                        print(f"✓ PyAudioWPatch input stream started: {input_device_name}")
                        print(f"  Sample rate: {sample_rate} Hz, Channels: {channels}")
                        print(f"  Stream active: {pyaudio_stream.is_active()}")
                        
                        # Store original sample rate BEFORE measurement (capture thread may update it)
                        original_sample_rate = sample_rate
                        
                        # Initialize flag to track if streams were already started during restart
                        streams_already_started = False
                        
                        # For virtual cables, skip sample rate measurement and use device's reported rate directly
                        # Virtual cables provide raw audio and their reported rates are accurate - this makes startup much faster!
                        if using_virtual_cable:
                            # Check if this virtual cable matches the default output
                            virtual_cable_is_default = False
                            if default_output_name and input_device_name:
                                device_base = input_device_name.replace('[Loopback]', '').replace('(Loopback)', '').strip()
                                default_base = default_output_name.strip()
                                if (default_base.lower() in device_base.lower() or 
                                    device_base.lower() in default_base.lower() or
                                    device_base.lower() == default_base.lower()):
                                    virtual_cable_is_default = True
                            
                            # Set flag to skip measurement in capture thread
                            skip_sample_rate_measurement['skip'] = True
                            # Start capture thread (still needed for audio capture, just skip measurement)
                            capture_thread = threading.Thread(target=pyaudio_capture_thread, daemon=True)
                            capture_thread.start()
                            print("✓ PyAudioWPatch capture thread started")
                            print("  ⚡ SKIPPING sample rate measurement for Virtual Audio Cable (using device rate directly)")
                            print(f"  ✓ Using device's reported rate: {sample_rate} Hz (raw audio - no measurement needed)")
                            # Mark as measured with the device rate to prevent restart
                            actual_measured_rate['measured'] = True
                            actual_measured_rate['rate'] = sample_rate
                            actual_measured_rate['exact_rate'] = float(sample_rate)  # Store exact rate
                            
                            # If virtual cable is NOT the default, wait a few seconds and check if we're getting audio
                            # If silent, fall back to default loopback
                            if not virtual_cable_is_default:
                                print(f"\n  ⚠ Virtual cable is not default output - checking if it's receiving audio...")
                                print(f"  ⚠ Waiting {VIRTUAL_CABLE_AUDIO_CHECK_WAIT} seconds to detect audio...")
                                time.sleep(VIRTUAL_CABLE_AUDIO_CHECK_WAIT)
                                
                                # Check if we've captured any audio with significant level
                                with buffer_lock:
                                    buffer_size = len(audio_buffer)
                                
                                # Check the last few chunks for audio level
                                audio_detected = False
                                if buffer_size > 0:
                                    # Check the most recent chunk
                                    try:
                                        with buffer_lock:
                                            if len(audio_buffer) > 0:
                                                last_chunk = audio_buffer[-1]
                                                max_level = np.abs(last_chunk).max()
                                                if max_level > SILENCE_THRESHOLD:  # Significant audio detected
                                                    audio_detected = True
                                    except:
                                        pass
                                
                                if not audio_detected:
                                    print(f"\n  ⚠⚠⚠ WARNING: Virtual cable is SILENT (not receiving audio)!")
                                    print(f"  ⚠ This is because it's not set as the default Windows output.")
                                    print(f"  ⚠ Falling back to default WASAPI loopback for audio capture...")
                                    print(f"  ⚠ NOTE: Default loopback is NOT raw audio (affected by Windows volume)")
                                    print(f"  💡 To get RAW audio: Set '{input_device_name.replace('[Loopback]', '').strip()}' as default output\n")
                                    
                                    # Close the virtual cable stream
                                    try:
                                        if pyaudio_stream:
                                            pyaudio_stream.stop_stream()
                                            pyaudio_stream.close()
                                            pyaudio_stream = None
                                    except:
                                        pass
                                    
                                    # Wait for capture thread to exit
                                    if capture_thread.is_alive():
                                        capture_thread.join(timeout=2.0)
                                    
                                    # Clear the buffer
                                    with buffer_lock:
                                        audio_buffer.clear()
                                        # CRITICAL: Reset read_index for all devices when buffer is cleared
                                        # This ensures devices start from the beginning when buffer is recreated
                                        for device_num in device_read_indices:
                                            device_read_indices[device_num] = 0
                                    
                                    # Fall back to default WASAPI loopback
                                    using_virtual_cable = False
                                    try:
                                        wasapi_loopback = p.get_default_wasapi_loopback()
                                        pyaudio_input_device = wasapi_loopback['index']
                                        input_device_name = wasapi_loopback['name']
                                        sample_rate = int(wasapi_loopback['defaultSampleRate'])
                                        channels = 2
                                        
                                        # Try to open default loopback
                                        stream_created = False
                                        for alt_rate in [sample_rate, 44100, 48000, 96000, 192000]:
                                            try:
                                                pyaudio_stream = p.open(
                                                    format=pyaudiowpatch.paInt16,
                                                    channels=channels,
                                                    rate=alt_rate,
                                                    input=True,
                                                    input_device_index=pyaudio_input_device,
                                                    frames_per_buffer=1024,
                                                    stream_callback=None
                                                )
                                                sample_rate = alt_rate
                                                stream_created = True
                                                print(f"✓ Using default WASAPI loopback: {input_device_name} at {sample_rate} Hz")
                                                break
                                            except:
                                                continue
                                        
                                        if not stream_created:
                                            raise Exception("Failed to open default WASAPI loopback after virtual cable fallback")
                                        
                                        # Restart the stream
                                        pyaudio_stream.start_stream()
                                        
                                        # Restart capture thread with measurement enabled
                                        skip_sample_rate_measurement['skip'] = False
                                        actual_measured_rate['measured'] = False
                                        actual_measured_rate['rate'] = sample_rate
                                        capture_thread = threading.Thread(target=pyaudio_capture_thread, daemon=True)
                                        capture_thread.start()
                                        print("✓ PyAudioWPatch capture thread restarted (with measurement)")
                                        
                                        # Update original_sample_rate for restart logic
                                        original_sample_rate = sample_rate
                                        
                                    except Exception as e:
                                        print(f"✗ Failed to fall back to default loopback: {e}")
                                        import traceback
                                        traceback.print_exc()
                                        raise Exception("Could not create audio capture stream after virtual cable fallback")
                                else:
                                    print(f"  ✓ Audio detected from virtual cable - continuing with raw audio capture!")
                        else:
                            # Start capture thread
                            capture_thread = threading.Thread(target=pyaudio_capture_thread, daemon=True)
                            capture_thread.start()
                            print("✓ PyAudioWPatch capture thread started")
                            
                            # CRITICAL: Wait for sample rate measurement BEFORE starting output streams
                            # This prevents audio from playing at wrong speed initially
                            # Note: Large chunks (131072 frames) at high rates (192000 Hz) take longer
                            # 131072 frames at 192000 Hz = ~0.68 seconds per chunk
                            # 10 chunks = ~6.8 seconds, so wait up to 15 seconds to be safe
                            print("  ⚠ CRITICAL: Waiting for sample rate measurement BEFORE starting output streams...")
                            print("  (This prevents audio from playing at wrong speed - may take up to 15 seconds)")
                            print("  (Reading 10 chunks to measure actual rate from chunk timing)")
                            
                            # Wait for sample rate measurement to complete
                            # (measurement happens in capture thread, might take a moment for large chunks)
                            max_wait_attempts = 30  # 15 seconds total (increased from 20)
                            measurement_complete = False
                            for attempt in range(max_wait_attempts):
                                if actual_measured_rate['measured']:
                                    print(f"  ✓✓✓ Measurement complete after {attempt * 0.5:.1f} seconds - output streams can now start at correct rate")
                                    measurement_complete = True
                                    break
                                time.sleep(0.5)  # Wait 0.5 seconds between checks
                            
                            if not measurement_complete:
                                print(f"  ⚠⚠⚠ WARNING: Measurement not complete after {max_wait_attempts * 0.5} seconds")
                                print(f"  ⚠⚠⚠ Starting output streams with initial rate ({sample_rate} Hz) - may need restart if rate differs")
                                print(f"  ⚠⚠⚠ Audio may play at wrong speed until measurement completes and streams restart")
                            else:
                                # Update sample_rate to measured rate immediately so output streams use correct rate
                                if actual_measured_rate['measured']:
                                    measured_rate = actual_measured_rate['rate']
                                    exact_measured = actual_measured_rate.get('exact_rate', float(measured_rate))
                                    rate_diff = abs(measured_rate - original_sample_rate)
                                    if rate_diff > 0.5:
                                        print(f"  ⚠ Sample rate differs: measured={measured_rate} Hz (exact: {exact_measured:.6f} Hz), original={original_sample_rate} Hz")
                                        print(f"  ⚠ Output streams will be created with measured rate to prevent speed issues")
                                        sample_rate = measured_rate  # Update immediately so output streams use correct rate
                                    else:
                                        print(f"  ✓ Sample rate matches: {measured_rate} Hz (exact: {exact_measured:.6f} Hz)")
                        
                        # Check if sample rate was updated and restart output streams if needed
                        exact_rate = actual_measured_rate.get('exact_rate', actual_measured_rate['rate'])
                        print(f"  Checking measurement results: measured={actual_measured_rate['measured']}, rate={actual_measured_rate['rate']} Hz, exact={exact_rate:.6f} Hz, original={original_sample_rate} Hz, current={sample_rate} Hz")
                        
                        # Always restart if measured rate differs from what output streams were created with
                        # Check against original_sample_rate (what streams were created with) not current sample_rate
                        rate_diff = abs(actual_measured_rate['rate'] - original_sample_rate)
                        # Also check if sample_rate was updated but streams weren't recreated yet
                        streams_need_restart = False
                        if actual_measured_rate['measured'] and rate_diff > 0.5:  # More than 0.5 Hz difference
                            streams_need_restart = True
                        elif actual_measured_rate['measured'] and abs(sample_rate - original_sample_rate) > 0.5:
                            # sample_rate was updated but streams might not have been recreated
                            streams_need_restart = True
                        
                        if streams_need_restart:
                            measured_rate = actual_measured_rate['rate']
                            exact_measured = actual_measured_rate.get('exact_rate', float(measured_rate))
                            print(f"\n⚠⚠⚠ RESTARTING OUTPUT STREAMS WITH EXACT MEASURED RATE ⚠⚠⚠")
                            print(f"  Measured exact rate: {exact_measured:.6f} Hz")
                            print(f"  Measured rounded rate: {measured_rate} Hz (for device compatibility)")
                            print(f"  Original rate: {original_sample_rate} Hz")
                            print(f"  Difference: {rate_diff:.1f} Hz ({exact_measured/original_sample_rate:.6f}x speed)")
                            print(f"  Restarting output streams at {measured_rate} Hz (exact: {exact_measured:.6f} Hz)...\n")
                            
                            # Stop existing output streams (use output_streams since started_streams may not exist yet)
                            for stream, device_name, device_num in output_streams:
                                try:
                                    # Only stop if stream was started
                                    if hasattr(stream, 'active') and stream.active:
                                        stream.stop()
                                    stream.close()
                                except:
                                    pass
                            
                            # Recreate output streams with EXACT measured rate
                            sample_rate = measured_rate
                            exact_rate = actual_measured_rate.get('exact_rate', float(measured_rate))
                            new_output_streams = []
                            for device_idx, device_num, volume in devices_to_use:
                                try:
                                    device_info = sd.query_devices(device_idx)
                                    device_name = device_info['name']
                                    device_max_channels = device_info.get('max_output_channels', 2)
                                    device_channels = min(output_channels, device_max_channels)
                                    
                                    # Use the exact measured rate (devices may round, but we request exact)
                                    # Note: Most devices only support integer rates, so we use rounded rate
                                    # but the measurement ensures we're as close as possible to the actual input rate
                                    output_callback = make_output_callback(device_num)
                                    output_stream = sd.OutputStream(
                                        device=device_idx,
                                        channels=device_channels,
                                        samplerate=sample_rate,  # Use rounded rate (device compatibility)
                                        callback=output_callback,
                                        dtype=np.float32,
                                        blocksize=1024
                                    )
                                    
                                    # Verify the stream is using the requested rate
                                    actual_stream_rate = output_stream.samplerate
                                    if abs(actual_stream_rate - sample_rate) > 0.5:
                                        print(f"  ⚠ Device {device_num} using {actual_stream_rate} Hz instead of {sample_rate} Hz")
                                        print(f"    Speed factor: {actual_stream_rate/exact_rate:.6f}x (may cause slight speed difference)")
                                    else:
                                        print(f"  ✓ Device {device_num} using {actual_stream_rate} Hz (matches requested {sample_rate} Hz)")
                                        print(f"    Exact input rate: {exact_rate:.6f} Hz, Output rate: {actual_stream_rate} Hz")
                                        print(f"    Speed factor: {actual_stream_rate/exact_rate:.6f}x (should be very close to 1.0)")
                                    
                                    new_output_streams.append((output_stream, device_name, device_num))
                                    print(f"✓ Recreated output stream for Device {device_num} at {sample_rate} Hz (exact input: {exact_rate:.6f} Hz)")
                                except Exception as e:
                                    print(f"✗ Failed to recreate stream for Device {device_num}: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            # Restart all streams
                            started_streams = []
                            for stream, device_name, device_num in new_output_streams:
                                try:
                                    stream.start()
                                    started_streams.append((stream, device_name, device_num))
                                    print(f"✓ Restarted Device {device_num} at {sample_rate} Hz")
                                except Exception as e:
                                    print(f"✗ Failed to restart Device {device_num}: {e}")
                            
                            # Update stored streams - use new_output_streams if restart succeeded, otherwise keep original
                            if started_streams:
                                output_streams = new_output_streams
                                self.passthrough_streams = [pyaudio_stream] + [stream for stream, _, _ in started_streams]
                                print(f"✓✓✓ Streams restarted successfully at {sample_rate} Hz (exact input: {exact_rate:.6f} Hz) - audio should now play at correct speed! ✓✓✓\n")
                                # Mark that streams are already started to skip the normal start below
                                streams_already_started = True
                            else:
                                print(f"⚠⚠⚠ WARNING: All output streams failed to restart! Keeping original streams. ⚠⚠⚠\n")
                                # Don't update output_streams or passthrough_streams - keep originals
                                # Still need to start the original streams
                                streams_already_started = False
                        elif actual_measured_rate['measured']:
                            exact_rate = actual_measured_rate.get('exact_rate', actual_measured_rate['rate'])
                            if abs(actual_measured_rate['rate'] - original_sample_rate) <= 0.5:
                                print(f"  ✓ Sample rate measurement complete: {actual_measured_rate['rate']} Hz (exact: {exact_rate:.6f} Hz)")
                                print(f"    Matches original rate: {original_sample_rate} Hz (difference: {abs(actual_measured_rate['rate'] - original_sample_rate):.1f} Hz)")
                            else:
                                print(f"  ⚠ Sample rate measured but restart may be needed")
                                print(f"    Measured: {actual_measured_rate['rate']} Hz (exact: {exact_rate:.6f} Hz)")
                                print(f"    Original: {original_sample_rate} Hz")
                        else:
                            print(f"  ⚠ Sample rate measurement not complete yet - may need more time")
                            print(f"    Will check again and restart streams if rate differs")
                        
                        with buffer_lock:
                            initial_buffer_size = len(audio_buffer)
                        print(f"  Initial buffer size: {initial_buffer_size} chunks")
                        
                        # Ready mode: Start immediately without waiting for audio
                        ready_mode = self.passthrough_ready_mode.get()
                        if ready_mode:
                            print("  ✓ Ready Mode: Starting output streams immediately - waiting for audio...")
                            # Update status and indicator immediately
                            def update_ready_ui():
                                self.passthrough_status_label.config(
                                    text="Ready - Waiting for audio...", fg="green"
                                )
                                self.ready_mode_indicator.config(
                                    text="🟢 READY MODE ACTIVE\n\nAll systems ready - Audio will play instantly when detected!",
                                    fg=self.colors['accent_success'],
                                    bg=self.colors['bg_secondary']
                                )
                                self.ready_mode_indicator.update()  # Force update
                            self.root.after(0, update_ready_ui)
                        else:
                            if initial_buffer_size == 0:
                                print("  WARNING: No audio captured yet - make sure audio is playing on the loopback device!")
                    else:
                        # Start sounddevice stream
                        input_stream.start()
                        print(f"✓ Sounddevice input stream started: {input_device_name}")
                        streams_already_started = False
                    
                    # Ready mode: Start streams immediately without waiting for audio
                    ready_mode = self.passthrough_ready_mode.get()
                    
                    # Only start streams if they weren't already started during restart
                    if not streams_already_started:
                        # APPROACH 1: Pre-buffer with simultaneous start
                        print("  ⏳ Pre-buffering data for synchronization...")
                        max_latency_ms = max(device_latencies.values()) * 1000.0
                        max_latency_seconds = max_latency_ms / 1000.0
                        
                        # Calculate how many chunks we need (based on max latency)
                        chunks_per_second = sample_rate / 65536.0  # 65536 frames per chunk
                        required_chunks = int(max_latency_seconds * chunks_per_second) + 3  # Add 3 chunks buffer for safety
                        
                        # Wait for buffer to have enough chunks
                        buffer_wait_start = time.time()
                        buffer_wait_timeout = 10.0  # Max 10 seconds to wait for buffer
                        while (len(audio_buffer) < required_chunks and 
                               time.time() - buffer_wait_start < buffer_wait_timeout and 
                               self.passthrough_active):
                            time.sleep(0.05)  # Check every 50ms
                        
                        if not self.passthrough_active:
                            print("  ⚠ Passthrough stopped during buffer wait - aborting stream start")
                            return
                        
                        if len(audio_buffer) < required_chunks:
                            print(f"  ⚠ Warning: Buffer only has {len(audio_buffer)} chunks (need {required_chunks}) - starting anyway")
                        else:
                            print(f"  ✓ Buffer ready: {len(audio_buffer)} chunks (required: {required_chunks})")
                        
                        print(f"  ✓ Pre-buffering complete - starting output streams for synchronized playback")
                        
                        # CRITICAL: Set global start time BEFORE starting any streams (for perfect sync)
                        # Calculate optimal offset: max_latency + buffer for stream initialization
                        # This ensures all devices use the same reference time for delay calculations
                        max_latency_seconds = max_latency if device_latencies else 0.1
                        stream_init_buffer = 0.15  # 150ms buffer for stream initialization and stabilization
                        optimal_offset = max(stream_init_buffer, max_latency_seconds + 0.05)  # At least 50ms more than max latency
                        global_stream_start_time[0] = time.time() + optimal_offset
                        print(f"\n  ═══ SYNCHRONIZATION SETUP ═══")
                        print(f"  Max device latency: {max_latency_seconds*1000:.1f}ms")
                        print(f"  Stream init buffer: {stream_init_buffer*1000:.0f}ms")
                        print(f"  Optimal offset: {optimal_offset*1000:.1f}ms")
                        print(f"  ✓ Global stream start time: {global_stream_start_time[0]:.6f}")
                        print(f"    (Current time: {time.time():.6f}, Offset: {optimal_offset*1000:.1f}ms)")
                        print(f"    All devices will use this as reference for time-based delays")
                        
                        # Store device-specific start times for verification
                        device_start_times_absolute = {}
                        for device_num, delay_seconds in device_start_times.items():
                            if delay_seconds is not None and delay_seconds > 0:
                                device_start_times_absolute[device_num] = global_stream_start_time[0] + delay_seconds
                                print(f"    Device {device_num}: Will start at {device_start_times_absolute[device_num]:.6f} (delay: {delay_seconds*1000:.1f}ms)")
                            else:
                                device_start_times_absolute[device_num] = global_stream_start_time[0]
                                print(f"    Device {device_num}: Will start at {device_start_times_absolute[device_num]:.6f} (no delay - highest latency)")
                        print(f"  ════════════════════════════════\n")
                        
                        if ready_mode:
                            print("  ✓ Ready Mode: Starting output streams immediately (no audio detection wait)")
                        
                        # CRITICAL: Start ALL streams as quickly as possible (collect commands first, then execute)
                        started_streams = []
                        start_commands = [(stream, device_name, device_num) for stream, device_name, device_num in output_streams]
                        
                        # CRITICAL: Start all streams in rapid succession with timing measurement
                        stream_start_times_actual = {}  # Track actual start times for verification
                        start_batch_time = time.time()
                        
                        for stream, device_name, device_num in start_commands:
                            try:
                                stream_start_before = time.time()
                                stream.start()
                                stream_start_after = time.time()
                                stream_start_times_actual[device_num] = stream_start_after
                                started_streams.append((stream, device_name, device_num))
                                
                                start_duration = (stream_start_after - stream_start_before) * 1000.0
                                print(f"✓ Output stream started for Device {device_num}: {device_name} (start took {start_duration:.2f}ms)")
                                
                                # CRITICAL: Verify actual sample rate AFTER stream is started
                                try:
                                    actual_rate = stream.samplerate
                                    if actual_rate != sample_rate:
                                        print(f"  ⚠⚠⚠ CRITICAL WARNING: Device {device_num} ({device_name})")
                                        print(f"    Requested {sample_rate} Hz but stream is using {actual_rate} Hz!")
                                        speed_factor = actual_rate / sample_rate
                                        print(f"    ⚠⚠⚠ Audio will play at {speed_factor:.3f}x speed ({'SLOWED DOWN' if speed_factor < 1.0 else 'SPED UP'})!")
                                        print(f"    ⚠⚠⚠ This is a device driver limitation - device doesn't support {sample_rate} Hz")
                                        print(f"    ⚠⚠⚠ SOLUTION: Use a different output device that supports {sample_rate} Hz")
                                        print(f"    ⚠⚠⚠ Expected callbacks: ~{sample_rate/1024:.1f}/sec, Actual: ~{actual_rate/1024:.1f}/sec")
                                    else:
                                        print(f"  ✓ Device {device_num} verified: Using correct sample rate ({actual_rate} Hz)")
                                        print(f"    Expected callbacks: ~{actual_rate/1024:.1f}/sec")
                                except Exception as e:
                                    print(f"  ⚠ Could not verify sample rate for Device {device_num}: {e}")
                                    print(f"    Assuming stream is using requested rate: {sample_rate} Hz")
                                
                                # Verify stream is actually active
                                if hasattr(stream, 'active'):
                                    is_active = stream.active
                                    print(f"  Stream active status: {is_active}")
                                    if not is_active:
                                        print(f"  ⚠ WARNING: Stream for Device {device_num} is not active!")
                                else:
                                    print(f"  (Cannot check active status - stream object doesn't have 'active' attribute)")
                            except Exception as e:
                                print(f"✗ ERROR: Failed to start output stream for Device {device_num} ({device_name}): {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Log stream start timing analysis
                        if len(stream_start_times_actual) > 1:
                            start_batch_duration = (time.time() - start_batch_time) * 1000.0
                            print(f"\n  ═══ STREAM START TIMING ═══")
                            print(f"  Total time to start all streams: {start_batch_duration:.2f}ms")
                            device_nums_sorted = sorted(stream_start_times_actual.keys())
                            if len(device_nums_sorted) >= 2:
                                time_diff = (stream_start_times_actual[device_nums_sorted[1]] - stream_start_times_actual[device_nums_sorted[0]]) * 1000.0
                                print(f"  Time between first and last stream start: {time_diff:.2f}ms")
                                if time_diff > 10.0:
                                    print(f"  ⚠ WARNING: Large gap between stream starts - may affect synchronization")
                            print(f"  ════════════════════════════════\n")
                        
                        # Update passthrough_streams with started streams
                        if pyaudio_stream is not None:
                            self.passthrough_streams = [pyaudio_stream] + [stream for stream, _, _ in started_streams]
                        elif input_stream is not None:
                            self.passthrough_streams = [input_stream] + [stream for stream, _, _ in started_streams]
                    
                    # Start monitoring thread to verify audio is playing
                    def monitor_audio_playback():
                        """Monitor that audio is actually playing on both devices."""
                        time.sleep(3)  # Wait for streams to start
                        check_count = 0
                        while self.passthrough_active:
                            check_count += 1
                            time.sleep(MONITOR_CHECK_INTERVAL)
                            
                            # Check buffer status
                            with buffer_lock:
                                buffer_size = len(audio_buffer)
                            
                            # Check stream status
                            active_streams = 0
                            stream_status = {}
                            for stream, device_name, device_num in started_streams:
                                try:
                                    # Check if stream is still running by checking if it's in the streams list
                                    # Also check the active property if available
                                    is_active = True  # Assume active by default
                                    if hasattr(stream, 'active'):
                                        try:
                                            is_active = stream.active
                                        except:
                                            # If we can't check active, assume it's active if callbacks are happening
                                            callback_count = output_level_counters.get(device_num, 0)
                                            is_active = callback_count > 0
                                    
                                    stream_status[device_num] = is_active
                                    if is_active:
                                        active_streams += 1
                                    else:
                                        callback_count = output_level_counters.get(device_num, 0)
                                        print(f"⚠ Device {device_num} ({device_name}) stream reports NOT active (but {callback_count} callbacks received)")
                                except Exception as e:
                                    print(f"⚠ Error checking stream status for Device {device_num}: {e}")
                                    stream_status[device_num] = None
                            
                            print(f"\n=== Audio Playback Health Check #{check_count} ===")
                            print(f"  Buffer size: {buffer_size} chunks")
                            print(f"  Active output streams: {active_streams}/{len(started_streams)}")
                            print(f"  Pass-through active: {self.passthrough_active}")
                            
                            if buffer_size == 0:
                                print(f"  ⚠ WARNING: Buffer is empty - no audio being captured!")
                            elif buffer_size < 10:
                                print(f"  ⚠ WARNING: Buffer is very low ({buffer_size} chunks) - may cause audio dropouts")
                            
                            if active_streams < len(started_streams):
                                print(f"  ⚠ WARNING: Not all output streams are active!")
                            
                            # Check output levels from callbacks - verify sustained output
                            for device_num in [1, 2]:  # Check both devices explicitly
                                counter = output_level_counters.get(device_num, 0)
                                is_active = stream_status.get(device_num, None)
                                
                                # Expected callbacks: at sample_rate Hz, CALLBACK_FRAMES frames per callback
                                expected_calls_per_sec = sample_rate / CALLBACK_FRAMES
                                expected_min = int(check_count * MONITOR_CHECK_INTERVAL * expected_calls_per_sec * 0.8)  # 80% of expected
                                elapsed_seconds = check_count * MONITOR_CHECK_INTERVAL
                                
                                if counter == 0:
                                    print(f"  ⚠ WARNING: Device {device_num} callback has NEVER been called!")
                                elif counter < expected_min:
                                    print(f"  ⚠ WARNING: Device {device_num} callback called only {counter} times (expected ~{expected_min} over {elapsed_seconds}s)")
                                else:
                                    # Calculate callbacks per second
                                    callbacks_per_sec = counter / elapsed_seconds
                                    expected_per_sec = sample_rate / CALLBACK_FRAMES
                                    
                                    if callbacks_per_sec >= expected_per_sec * 0.8:  # Within 80% of expected
                                        print(f"  ✓✓✓ Device {device_num}: {counter} callbacks ({callbacks_per_sec:.1f}/sec) - SUSTAINED OUTPUT! ✓✓✓")
                                        print(f"    ✓ Audio should be playing continuously on Device {device_num}!")
                                    else:
                                        print(f"  ⚠ Device {device_num}: {counter} callbacks ({callbacks_per_sec:.1f}/sec) - may have interruptions")
                                
                                # Check read indices and remainder buffers
                                with buffer_lock:
                                    read_idx = device_read_indices.get(device_num, 0)
                                    remainder_info = ""
                                    rem = remainder_buffers.get(device_num)
                                    if rem is not None:
                                        remainder_info = f", remainder={len(rem)} frames"
                                    print(f"    Device {device_num} read_index: {read_idx}, buffer_size: {len(audio_buffer)}{remainder_info}")
                                
                                if is_active is False and counter > 0:
                                    print(f"    ⚠ Note: stream.active reports False, but {counter} callbacks received - stream IS working!")
                    
                    monitor_thread = threading.Thread(target=monitor_audio_playback, daemon=True)
                    monitor_thread.start()
                    print("✓ Audio monitoring thread started")
                    
                    if not started_streams:
                        raise Exception("No output streams could be started. Check device selection and permissions.")
                    
                    # Update stored streams to only include successfully started ones
                    self.passthrough_streams = [input_stream] + [stream for stream, _, _ in started_streams]
                    
                    # Update status based on ready mode
                    ready_mode = self.passthrough_ready_mode.get()
                    if ready_mode:
                        def update_ready_active():
                            self.passthrough_status_label.config(
                                text=f"Ready Mode Active - Routing to {len(devices_to_use)} device(s) (Waiting for audio...)", fg="green"
                            )
                            # Ensure READY indicator is still showing
                            self.ready_mode_indicator.config(
                                text="🟢 READY MODE ACTIVE\n\nAll systems ready - Audio will play instantly when detected!",
                                fg=self.colors['accent_success'],
                                bg=self.colors['bg_secondary']
                            )
                            self.ready_mode_indicator.update()  # Force update
                        self.root.after(0, update_ready_active)
                    else:
                        self.root.after(0, lambda: self.passthrough_status_label.config(
                            text=f"Pass-through active - Routing to {len(devices_to_use)} device(s)", fg="green"
                        ))
                        # Clear ready indicator for normal mode
                        self.root.after(0, lambda: self.ready_mode_indicator.config(
                            text="",
                            bg=self.colors['bg_secondary']
                        ))
                    
                    # Keep running while active - monitor and restart streams if they stop
                    last_stream_check = time.time()
                    last_capture_check = time.time()
                    last_buffer_size = 0
                    last_default_device = None
                    restart_count = 0
                    max_restarts_before_warning = 10  # Warn after 10 restarts, but keep trying
                    last_health_check = time.time()
                    HEALTH_CHECK_INTERVAL = 300.0  # 5 minutes - periodic health check
                    passthrough_start_time = time.time()  # Track when passthrough started
                    
                    while self.passthrough_active:
                        time.sleep(0.1)
                        current_time = time.time()
                        
                        # Check capture thread every 5 seconds - restart if it's dead or not capturing
                        if pyaudio_stream is not None and (current_time - last_capture_check) > 5.0:
                            last_capture_check = current_time
                            
                            # Check if capture thread is alive - restart if dead
                            if not capture_thread.is_alive():
                                restart_count += 1
                                if restart_count <= max_restarts_before_warning:
                                    print(f"⚠⚠⚠ WARNING: Capture thread is not alive! Restarting (attempt #{restart_count})...")
                                elif restart_count == max_restarts_before_warning + 1:
                                    print(f"⚠⚠⚠ WARNING: Capture has restarted {restart_count} times!")
                                    print("⚠⚠⚠ This may indicate an underlying issue, but capture will continue...")
                                else:
                                    # Only log every 10th restart after warning to avoid spam
                                    if restart_count % 10 == 0:
                                        print(f"⚠ Capture restarted {restart_count} times (still running...)")
                                
                                try:
                                    # Stop and close old stream
                                    if pyaudio_stream and pyaudio_stream.is_active():
                                        pyaudio_stream.stop_stream()
                                    if pyaudio_stream:
                                        pyaudio_stream.close()
                                    pyaudio_stream = None
                                except Exception as e:
                                    print(f"⚠ Error closing old stream: {e}")
                                
                                # Restart capture thread immediately (don't break - keep monitoring)
                                try:
                                    # Restart stream if it's not active
                                    if pyaudio_stream is not None:
                                        if not pyaudio_stream.is_active():
                                            try:
                                                pyaudio_stream.start_stream()
                                                print(f"✓ PyAudio stream restarted")
                                            except:
                                                # Stream might be closed, try to recreate it
                                                try:
                                                    pyaudio_stream.close()
                                                except:
                                                    pass
                                                # Will need to break and reinitialize - stream recreation is complex
                                                print("⚠ Stream needs full restart - breaking to reinitialize...")
                                                break
                                    
                                    # Restart capture thread
                                    capture_thread = threading.Thread(target=pyaudio_capture_thread, daemon=True)
                                    capture_thread.start()
                                    print(f"✓ Capture thread restarted")
                                    
                                    # Reset buffer update time to prevent immediate stuck detection
                                    last_buffer_update_time = time.time()
                                    
                                except Exception as restart_error:
                                    print(f"✗ Failed to restart capture: {restart_error}")
                                    import traceback
                                    traceback.print_exc()
                                    # If restart fails, break to trigger full reinitialization
                                    break
                            
                            # CRITICAL: Check if buffer is being updated (capture thread may be stuck in blocking read)
                            # This detects the case where the thread is alive but stuck in pyaudio_stream.read()
                            time_since_last_update = current_time - last_buffer_update_time
                            CAPTURE_STUCK_TIMEOUT = 20.0  # If no chunks added for 20 seconds, capture is stuck
                            
                            if time_since_last_update > CAPTURE_STUCK_TIMEOUT:
                                print(f"⚠⚠⚠ CRITICAL: No buffer updates for {time_since_last_update:.1f} seconds!")
                                print(f"⚠⚠⚠ Capture thread appears stuck (likely blocking in pyaudio_stream.read())")
                                print(f"⚠⚠⚠ Attempting to restart capture stream...")
                                
                                # Force restart the capture stream
                                try:
                                    if pyaudio_stream.is_active():
                                        pyaudio_stream.stop_stream()
                                    pyaudio_stream.close()
                                    pyaudio_stream = None
                                except Exception as e:
                                    print(f"⚠ Error closing stuck stream: {e}")
                                
                                # Wait for capture thread to exit (with timeout)
                                if capture_thread.is_alive():
                                    capture_thread.join(timeout=2.0)
                                    if capture_thread.is_alive():
                                        print("⚠⚠⚠ WARNING: Capture thread did not exit - may need manual restart")
                                
                                # Break to trigger restart in outer loop (unlimited restarts)
                                break
                            
                            # Check if buffer is growing (capture is working)
                            # CRITICAL: During silence, buffer size may stay constant (limited to 5 chunks)
                            # So we need to check if buffer is being UPDATED (timestamp), not just growing
                            with buffer_lock:
                                current_buffer_size = len(audio_buffer)
                            
                            # Only check buffer growth if we haven't had an update recently
                            # During silence, buffer updates continue (just limited size), so timestamp is more reliable
                            time_since_buffer_update = current_time - last_buffer_update_time
                            
                            # If buffer hasn't grown AND no updates for 10 seconds AND stream is inactive, restart
                            # This prevents false positives during silence (where buffer size stays constant)
                            if (current_buffer_size == last_buffer_size and 
                                last_buffer_size > 0 and 
                                time_since_buffer_update > 10.0 and  # No updates for 10 seconds
                                (pyaudio_stream is None or not pyaudio_stream.is_active())):
                                # Buffer not growing AND no updates AND stream inactive - capture likely stopped
                                print(f"⚠⚠⚠ WARNING: Buffer not growing (size={current_buffer_size}) and no updates for {time_since_buffer_update:.1f}s - capture may have stopped!")
                                print("⚠⚠⚠ Stream is not active - attempting restart...")
                                try:
                                    if pyaudio_stream and pyaudio_stream.is_active():
                                        pyaudio_stream.stop_stream()
                                    if pyaudio_stream:
                                        pyaudio_stream.close()
                                except:
                                    pass
                                break  # Exit to trigger restart
                            
                            last_buffer_size = current_buffer_size
                            
                            # Check if default audio device has changed (user switched audio source)
                            try:
                                current_default = sd.query_devices(kind='output')
                                current_default_name = current_default['name']
                                if last_default_device is not None and current_default_name != last_default_device:
                                    print(f"⚠⚠⚠ WARNING: Default audio device changed from '{last_default_device}' to '{current_default_name}'!")
                                    print("⚠⚠⚠ Restarting capture to use new device...")
                                    try:
                                        if pyaudio_stream.is_active():
                                            pyaudio_stream.stop_stream()
                                        pyaudio_stream.close()
                                    except:
                                        pass
                                    break  # Exit to trigger restart with new device
                                last_default_device = current_default_name
                            except:
                                pass  # Ignore errors checking default device
                        
                        # Check streams every 2 seconds and restart if they've stopped
                        if current_time - last_stream_check > 2.0:
                            last_stream_check = current_time
                            for stream, device_name, device_num in started_streams:
                                try:
                                    # Check if stream is still active
                                    if hasattr(stream, 'active'):
                                        is_active = stream.active
                                        callback_count = output_level_counters.get(device_num, 0)
                                        
                                        # If stream reports inactive but we're getting callbacks, it's probably fine
                                        # But if it's inactive AND no recent callbacks, restart it
                                        if not is_active:
                                            # Check if we've received callbacks recently
                                            last_callback_time = output_level_timers.get(device_num, 0)
                                            time_since_last_callback = current_time - last_callback_time
                                            
                                            if time_since_last_callback > 1.0 and callback_count > 0:
                                                # Stream stopped but was working - restart it
                                                print(f"⚠ Device {device_num} ({device_name}) stream stopped - restarting...")
                                                try:
                                                    stream.stop()
                                                    time.sleep(0.1)
                                                    stream.start()
                                                    
                                                    # CRITICAL: Recalculate read_index after stream restart to maintain sync
                                                    # Sync to SLOWEST device (min read_index) so restarted device rejoins without pulling group ahead.
                                                    # Scalable for many speakers: use min of all other devices, not first other.
                                                    with buffer_lock:
                                                        current_buffer_size = len(audio_buffer)
                                                        other_indices = [idx for dnum, idx in device_read_indices.items() if dnum != device_num]
                                                        slowest_other = min(other_indices) if other_indices else None
                                                        
                                                        if slowest_other is not None:
                                                            new_read_index = max(0, slowest_other)
                                                            device_read_indices[device_num] = min(new_read_index, current_buffer_size)
                                                            print(f"✓ Device {device_num} read_index reset to {device_read_indices[device_num]} (synced to slowest device at position {slowest_other})")
                                                        else:
                                                            device_read_indices[device_num] = min(current_buffer_size - 1, max(0, current_buffer_size - 5))
                                                            print(f"✓ Device {device_num} read_index reset to {device_read_indices[device_num]} (buffer_size={current_buffer_size}, no other device to sync with)")
                                                    
                                                    print(f"✓ Device {device_num} stream restarted successfully")
                                                except Exception as restart_error:
                                                    print(f"✗ Failed to restart Device {device_num} stream: {restart_error}")
                                                    import traceback
                                                    traceback.print_exc()
                                except Exception as check_error:
                                    # Don't let stream checking errors break the main loop
                                    pass
                        
                        # Periodic health check every 5 minutes to ensure long-term stability
                        if current_time - last_health_check > HEALTH_CHECK_INTERVAL:
                            last_health_check = current_time
                            runtime_minutes = (current_time - passthrough_start_time) / 60.0
                            
                            # Log health status
                            print(f"\n{'='*60}")
                            print(f"📊 PASSTHROUGH HEALTH CHECK ({runtime_minutes:.1f} minutes running)")
                            print(f"{'='*60}")
                            
                            # Check capture thread
                            if pyaudio_stream is not None:
                                capture_alive = capture_thread.is_alive() if 'capture_thread' in locals() else False
                                stream_active = pyaudio_stream.is_active() if pyaudio_stream else False
                                print(f"  Capture thread: {'✓ Alive' if capture_alive else '✗ Dead'}")
                                print(f"  Capture stream: {'✓ Active' if stream_active else '✗ Inactive'}")
                            else:
                                print(f"  Capture: ✗ Not initialized")
                            
                            # Check output streams
                            active_outputs = 0
                            for stream, device_name, device_num in started_streams:
                                try:
                                    if hasattr(stream, 'active') and stream.active:
                                        active_outputs += 1
                                except:
                                    pass
                            print(f"  Output streams: {active_outputs}/{len(started_streams)} active")
                            
                            # Check buffer
                            with buffer_lock:
                                buffer_size = len(audio_buffer)
                            print(f"  Buffer size: {buffer_size} chunks")
                            print(f"  Last buffer update: {time.time() - last_buffer_update_time:.1f} seconds ago")
                            
                            # Check restart count
                            if restart_count > 0:
                                print(f"  Restart count: {restart_count} (warnings after {max_restarts_before_warning})")
                            
                            print(f"{'='*60}\n")
                            
                            # If capture thread is dead or stream is inactive, trigger restart
                            if pyaudio_stream is not None:
                                capture_alive = capture_thread.is_alive() if 'capture_thread' in locals() else False
                                stream_active = pyaudio_stream.is_active() if pyaudio_stream else False
                                if not capture_alive or not stream_active:
                                    print(f"⚠⚠⚠ Health check detected issue - triggering restart...")
                                    try:
                                        if pyaudio_stream and pyaudio_stream.is_active():
                                            pyaudio_stream.stop_stream()
                                        if pyaudio_stream:
                                            pyaudio_stream.close()
                                    except:
                                        pass
                                    break  # Exit to trigger restart
                    
                    # Restore original audio mute state when passthrough ends
                    # Only restore if we actually muted the device (original_mute_state is not None)
                    if 'volume_control_available' in locals() and volume_control_available:
                        if 'original_mute_state' in locals() and original_mute_state is not None:
                            # We muted the device, so restore the original state
                            try:
                                from audio_volume_control import unmute_device_by_name, unmute_default_output, get_default_output_mute_state
                                # Try to unmute the specific device first
                                if 'device_to_mute_name' in locals() and device_to_mute_name:
                                    if unmute_device_by_name(device_to_mute_name):
                                        print(f"✓ Device unmuted: {device_to_mute_name}")
                                    else:
                                        # Fallback to default
                                        unmute_default_output()
                                        print("✓ Default device unmuted (fallback)")
                                else:
                                    # No specific device, use default
                                    # Restore original state
                                    current_state = get_default_output_mute_state()
                                    if current_state != original_mute_state:
                                        if original_mute_state:
                                            # Was muted, restore mute
                                            from audio_volume_control import mute_default_output
                                            mute_default_output()
                                        else:
                                            # Was unmuted, restore unmute
                                            unmute_default_output()
                                        print("✓ Original audio mute state restored")
                            except Exception as e:
                                print(f"⚠ Error restoring original audio state: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            # We didn't mute the device (smart muting skipped it), so don't unmute
                            print("ℹ Skipping unmute (device was not muted during passthrough)")
                    
                except Exception as e:
                    error_str = str(e)
                    error_type = type(e).__name__
                    print(f"⚠⚠⚠ Error in audio pass-through: {error_type}: {error_str}")
                    import traceback
                    traceback.print_exc()
                    
                    # Determine if this is a critical error that should stop passthrough
                    # Most errors are recoverable - just restart the inner loop
                    critical_errors = [
                        "No loopback device found",
                        "Could not find a working WASAPI loopback device",
                        "Failed to create any output streams",
                        "Missing Dependencies"
                    ]
                    is_critical = any(critical in error_str for critical in critical_errors)
                    
                    if is_critical:
                        # Critical error - stop passthrough
                        print("⚠⚠⚠ CRITICAL ERROR - stopping passthrough")
                        # Restore original audio mute state on error (only if we muted it)
                        if 'volume_control_available' in locals() and volume_control_available:
                            if 'original_mute_state' in locals() and original_mute_state is not None:
                                try:
                                    from audio_volume_control import unmute_device_by_name, unmute_default_output
                                    # Try to unmute the specific device
                                    if 'device_to_mute_name' in locals() and device_to_mute_name:
                                        unmute_device_by_name(device_to_mute_name)
                                    else:
                                        if original_mute_state is False:
                                            unmute_default_output()
                                    print("✓ Original audio source unmuted (error recovery)")
                                except Exception as e:
                                    print(f"⚠ Error unmuting on error recovery: {e}")
                            else:
                                print("ℹ Skipping unmute on error (device was not muted)")
                        
                        self.root.after(0, lambda: messagebox.showerror(
                            "Pass-Through Error",
                            f"Critical error in audio pass-through:\n\n{error_str}\n\n"
                            "Make sure:\n"
                            "- Stereo Mix is enabled in Windows Sound Settings\n"
                            "- Or use a virtual audio cable\n"
                            "- Output devices are properly selected"
                        ))
                        self.root.after(0, lambda: self.stop_audio_passthrough())
                        break  # Exit outer restart loop on critical errors
                    else:
                        # Recoverable error - just restart the inner loop
                        print(f"⚠ Recoverable error detected - will restart passthrough in 2 seconds...")
                        # Restore original audio mute state temporarily (only if we muted it)
                        if 'volume_control_available' in locals() and volume_control_available:
                            if 'original_mute_state' in locals() and original_mute_state is not None:
                                try:
                                    from audio_volume_control import unmute_device_by_name, unmute_default_output
                                    if 'device_to_mute_name' in locals() and device_to_mute_name:
                                        unmute_device_by_name(device_to_mute_name)
                                    elif original_mute_state is False:
                                        unmute_default_output()
                                except:
                                    pass  # Ignore errors during recovery
                        
                        # Continue to restart logic below (don't break)
                    
                except ImportError:
                    self.root.after(0, lambda: messagebox.showerror(
                        "Missing Dependencies",
                        "sounddevice and numpy are required for audio pass-through.\n\n"
                        "Install with: pip install sounddevice numpy"
                    ))
                    self.root.after(0, lambda: self.stop_audio_passthrough())
                    break  # Exit outer restart loop on import errors
                
                # If we get here, the inner loop exited (capture failed but not critical error)
                # Wait a moment before restarting to avoid rapid restart loops
                if self.passthrough_active:
                    print("⚠ Passthrough monitoring loop exited - will restart in 2 seconds...")
                    import time
                    time.sleep(2.0)
                    print("🔄 Restarting passthrough capture...")
        
        self.passthrough_thread = threading.Thread(target=passthrough_thread, daemon=True)
        self.passthrough_thread.start()
    
    def stop_audio_passthrough(self):
        """Stop audio pass-through."""
        if not self.passthrough_active:
            return
        
        # Update UI immediately (non-blocking)
        self.start_passthrough_btn.config(state=tk.NORMAL)
        self.stop_passthrough_btn.config(state=tk.DISABLED)
        self.passthrough_status_label.config(text="Stopping pass-through...", fg=self.colors['accent_warning'])
        # Clear ready mode indicator
        self.ready_mode_indicator.config(text="", bg=self.colors['bg_secondary'])
        
        # Set flag to stop the thread
        self.passthrough_active = False
        
        # Do cleanup in a background thread to avoid freezing GUI
        def cleanup_thread():
            try:
                # Round 9: Stop distributed computing components (in cleanup thread to avoid blocking)
                if DISTRIBUTED_AVAILABLE:
                    if self.master_node:
                        try:
                            self.master_node.stop()
                            print("Master Node stopped")
                        except Exception as e:
                            print(f"Error stopping Master Node: {e}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            self.master_node = None
                    
                    if self.fleet_node:
                        try:
                            self.fleet_node.disconnect()
                            print("Fleet Node disconnected")
                        except Exception as e:
                            print(f"Error disconnecting Fleet Node: {e}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            self.fleet_node = None
                # Give the main thread a moment to see the flag change
                import time
                time.sleep(0.1)
                
                # CRITICAL: Stop all output streams FIRST to prevent underflow errors
                # This must happen before stopping master node or capture stream
                streams_to_stop = list(self.passthrough_streams) if hasattr(self, 'passthrough_streams') else []
                for stream in streams_to_stop:
                    try:
                        if hasattr(stream, 'stop'):
                            stream.stop()
                    except Exception as e:
                        print(f"Error stopping stream: {e}")
                    except:
                        pass  # Ignore any other errors during shutdown
                    try:
                        if hasattr(stream, 'close'):
                            stream.close()
                    except Exception as e:
                        print(f"Error closing stream: {e}")
                    except:
                        pass  # Ignore any other errors during shutdown
                
                # Clear streams list immediately after stopping
                if hasattr(self, 'passthrough_streams'):
                    self.passthrough_streams = []
                
                # Stop PyAudio capture stream after output streams (to unblock any waiting reads)
                if hasattr(self, 'pyaudio_capture_stream') and self.pyaudio_capture_stream is not None:
                    try:
                        if hasattr(self.pyaudio_capture_stream, 'stop_stream'):
                            self.pyaudio_capture_stream.stop_stream()
                    except Exception as e:
                        print(f"Error stopping PyAudio capture stream: {e}")
                    except:
                        pass  # Ignore any other errors during shutdown
                    try:
                        if hasattr(self.pyaudio_capture_stream, 'close'):
                            self.pyaudio_capture_stream.close()
                    except Exception as e:
                        print(f"Error closing PyAudio capture stream: {e}")
                    except:
                        pass  # Ignore any other errors during shutdown
                    self.pyaudio_capture_stream = None
                
                # Wait for thread to finish (with timeout to prevent hanging)
                if hasattr(self, 'passthrough_thread') and self.passthrough_thread and self.passthrough_thread.is_alive():
                    self.passthrough_thread.join(timeout=2.0)
                    if self.passthrough_thread.is_alive():
                        print("⚠ Warning: Passthrough thread did not stop within timeout")
                
                # Restore original audio mute state (unmute if we muted it)
                # This is a backup in case the passthrough thread didn't restore it
                try:
                    from audio_volume_control import unmute_default_output, get_default_output_mute_state
                    current_state = get_default_output_mute_state()
                    if current_state is True:  # If still muted, unmute it
                        unmute_default_output()
                        print("✓ Original audio source unmuted (cleanup)")
                except Exception as e:
                    print(f"⚠ Could not restore original audio state: {e}")
                
                # Update UI on main thread (safely check if root exists)
                try:
                    if hasattr(self, 'root') and self.root:
                        self.root.after(0, lambda: self.passthrough_status_label.config(
                            text="✓ Pass-through stopped", 
                            fg=self.colors['text_secondary']
                        ))
                except Exception as e:
                    print(f"Error updating UI in cleanup: {e}")
                except:
                    pass  # Ignore any other errors
                
                print("Audio pass-through stopped")
                print("DEBUG: Cleanup thread finished - app should stay open")
                # Ensure we don't accidentally cause the process to exit
                # The cleanup thread should finish gracefully without affecting the main thread
            except Exception as e:
                print(f"Error in cleanup thread: {e}")
                import traceback
                traceback.print_exc()
                # Still update UI even if cleanup had errors
                try:
                    self.root.after(0, lambda: self.passthrough_status_label.config(
                        text="✓ Pass-through stopped", 
                        fg=self.colors['text_secondary']
                    ))
                except:
                    pass  # Ignore errors updating UI
            except BaseException as e:
                # Catch errors but don't let them close the app
                # Only re-raise KeyboardInterrupt (Ctrl+C) - let user exit if they want
                if isinstance(e, KeyboardInterrupt):
                    raise  # Re-raise KeyboardInterrupt to allow normal shutdown
                # Don't re-raise SystemExit - that would close the app when stop button is clicked
                print(f"Unexpected error in cleanup thread: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                # Still try to update UI
                try:
                    if hasattr(self, 'root') and self.root:
                        self.root.after(0, lambda: self.passthrough_status_label.config(
                            text="✓ Pass-through stopped", 
                            fg=self.colors['text_secondary']
                        ))
                except:
                    pass  # Ignore errors updating UI
        
        # Start cleanup in background thread (daemon=False to prevent app from closing)
        # The cleanup thread should finish gracefully without affecting the main thread
        cleanup_thread_obj = threading.Thread(target=cleanup_thread, daemon=False)
        cleanup_thread_obj.start()


def main():
    """Run the GUI application."""
    root = None
    try:
        root = tk.Tk()
        app = AudioSyncGUI(root)
        print("DEBUG: Starting mainloop - app should stay open")
        root.mainloop()
        print("DEBUG: mainloop exited - this should only happen when window is closed")
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except SystemExit:
        # Allow normal system exit
        raise
    except Exception as e:
        print(f"Fatal error in main: {e}")
        import traceback
        traceback.print_exc()
        # Try to keep the window open if possible
        try:
            if root:
                print("DEBUG: Attempting to restart mainloop after error")
                root.mainloop()
        except Exception as e2:
            print(f"DEBUG: Could not restart mainloop: {e2}")
        except:
            print("DEBUG: Could not restart mainloop (unknown error)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except SystemExit:
        # Allow normal system exit
        raise
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        print("DEBUG: Exception in __main__ - this should not cause app to exit")
        # Don't exit immediately - the error should have been handled in main()
        # Only show "Press Enter" if we really can't keep it open
        print("DEBUG: About to show 'Press Enter' prompt - app is exiting")
        try:
            input("Press Enter to exit...")  # Keep window open to see error
        except:
            pass  # Ignore errors in input() too