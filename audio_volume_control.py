"""
Windows Audio Volume Control
Provides functions to mute/unmute audio devices.
Uses direct COM access via comtypes (bypasses pycaw wrapper issues).
"""

import logging
import sys

logger = logging.getLogger("VolumeControl")

# Try to import comtypes (required for COM access)
comtypes_available = False
CLSCTX_ALL = None
POINTER = None
cast = None
GUID = None

try:
    import comtypes
    from comtypes import CLSCTX_ALL, GUID
    from ctypes import POINTER, cast
    comtypes_available = True
    logger.debug("comtypes available for volume control")
except ImportError as e:
    logger.debug(f"comtypes import failed: {e}")
    logger.warning("comtypes not available - cannot control Windows audio volume")
    logger.warning("Install with: pip install comtypes")

# Try to import pycaw for device name lookup and interface definitions (optional)
pycaw_available = False
AudioUtilities = None
ISimpleAudioVolume = None

try:
    from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
    pycaw_available = True
    logger.debug("pycaw available for device name lookup and interface definitions")
except ImportError:
    logger.debug("pycaw not available - will use COM directly for all operations")


def _get_default_device_via_com():
    """
    Get the default audio output device using COM directly.
    Returns the ISimpleAudioVolume interface for the default device.
    Uses pycaw's ISimpleAudioVolume interface definition if available.
    """
    if not comtypes_available:
        raise RuntimeError("comtypes not available")
    
    # Use pycaw's ISimpleAudioVolume interface if available, otherwise define it
    if ISimpleAudioVolume is not None:
        ISimpleAudioVolume_IID = ISimpleAudioVolume._iid_
    else:
        # ISimpleAudioVolume IID: 87CE5498-68D6-44E5-9215-6DA47EF883D8
        ISimpleAudioVolume_IID = GUID("{87CE5498-68D6-44E5-9215-6DA47EF883D8}")
    
    # MMDeviceEnumerator CLSID: BCDE0395-E52F-467C-8E3D-C4579291692E
    MMDeviceEnumerator_CLSID = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    
    # IMMDeviceEnumerator IID: A95664D2-9614-4F35-A746-DE8DB63617E6
    IMMDeviceEnumerator_IID = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    
    # IMMDevice IID: D666063F-1587-4E43-81F1-B948E807363F
    IMMDevice_IID = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
    
    try:
        # Define IMMDeviceEnumerator interface
        class IMMDeviceEnumerator(comtypes.IUnknown):
            _iid_ = IMMDeviceEnumerator_IID
            _methods_ = [
                comtypes.COMMETHOD([], comtypes.HRESULT, "EnumAudioEndpoints",
                    (['in'], comtypes.c_int, "dataFlow"),
                    (['in'], comtypes.c_uint, "dwStateMask"),
                    (['out'], POINTER(comtypes.POINTER(comtypes.IUnknown)), "ppDevices")),
                comtypes.COMMETHOD([], comtypes.HRESULT, "GetDefaultAudioEndpoint",
                    (['in'], comtypes.c_int, "dataFlow"),
                    (['in'], comtypes.c_int, "role"),
                    (['out'], POINTER(comtypes.POINTER(comtypes.IUnknown)), "ppEndpoint")),
            ]
        
        # Define IMMDevice interface (simplified - just need Activate)
        class IMMDevice(comtypes.IUnknown):
            _iid_ = IMMDevice_IID
            _methods_ = [
                comtypes.COMMETHOD([], comtypes.HRESULT, "Activate",
                    (['in'], GUID, "iid"),
                    (['in'], comtypes.c_uint, "dwClsCtx"),
                    (['in'], comtypes.POINTER(GUID), "pActivationParams"),
                    (['out'], POINTER(comtypes.POINTER(comtypes.IUnknown)), "ppInterface")),
            ]
        
        # Define ISimpleAudioVolume if pycaw not available
        if ISimpleAudioVolume is None:
            class ISimpleAudioVolume(comtypes.IUnknown):
                _iid_ = ISimpleAudioVolume_IID
                _methods_ = [
                    comtypes.COMMETHOD([], comtypes.HRESULT, "SetMasterVolume",
                        (['in'], comtypes.c_float, "level"),
                        (['in'], comtypes.POINTER(GUID), "EventContext")),
                    comtypes.COMMETHOD([], comtypes.HRESULT, "GetMasterVolume",
                        (['out'], POINTER(comtypes.c_float), "level")),
                    comtypes.COMMETHOD([], comtypes.HRESULT, "SetMute",
                        (['in'], comtypes.c_int, "Mute"),
                        (['in'], comtypes.POINTER(GUID), "EventContext")),
                    comtypes.COMMETHOD([], comtypes.HRESULT, "GetMute",
                        (['out'], POINTER(comtypes.c_int), "Mute")),
                ]
        
        # Create the MMDeviceEnumerator COM object
        from comtypes.client import CreateObject
        enumerator = CreateObject(MMDeviceEnumerator_CLSID, interface=IMMDeviceEnumerator_IID)
        
        # Get default audio endpoint (eRender = 0, eConsole = 0)
        # eRender = 0 means output device
        # eConsole = 0 means console session (not multimedia)
        default_device_ptr = comtypes.POINTER(IMMDevice)()
        enumerator.GetDefaultAudioEndpoint(0, 0, comtypes.byref(default_device_ptr))  # eRender, eConsole
        default_device = default_device_ptr
        
        # Activate ISimpleAudioVolume interface
        interface_ptr = comtypes.POINTER(comtypes.IUnknown)()
        default_device.Activate(ISimpleAudioVolume_IID, CLSCTX_ALL, None, comtypes.byref(interface_ptr))
        
        # Cast to ISimpleAudioVolume pointer
        if ISimpleAudioVolume is not None:
            # Use pycaw's interface definition
            volume = cast(interface_ptr, POINTER(ISimpleAudioVolume))
        else:
            # Use our own definition
            volume = cast(interface_ptr, POINTER(ISimpleAudioVolume))
        
        return volume
        
    except Exception as e:
        logger.error(f"Failed to get device via COM: {e}", exc_info=True)
        raise


def mute_device_by_name(device_name: str = None):
    """
    Mute the default Windows audio output device.
    Uses pycaw's EndpointVolume property (confirmed to work).
    
    Args:
        device_name: Name of device (for logging only - always mutes default)
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not pycaw_available:
        logger.warning("Cannot mute audio: pycaw not available. Install with: pip install pycaw")
        print("WARNING: Cannot mute audio: pycaw not available. Install with: pip install pycaw")
        return False
    
    try:
        default_device = AudioUtilities.GetSpeakers()
        default_name = default_device.FriendlyName
        
        # Use EndpointVolume property (confirmed to exist and work)
        volume = default_device.EndpointVolume
        volume.SetMute(1, None)
        is_muted = volume.GetMute()
        
        if is_muted:
            logger.info(f"Successfully muted default device: {default_name}")
            print(f"Successfully muted default audio device: {default_name}")
            return True
        else:
            logger.warning(f"Mute command sent but device is not muted: {default_name}")
            print(f"WARNING: Mute command sent but device '{default_name}' is not muted")
            return False
            
    except Exception as e:
        logger.error(f"Failed to mute audio device: {e}", exc_info=True)
        print(f"ERROR muting audio device: {e}")
        import traceback
        traceback.print_exc()
        return False


def mute_default_output():
    """
    Mute the default Windows audio output device.
    
    Returns:
        bool: True if successful, False otherwise
    """
    return mute_device_by_name(None)


def unmute_device_by_name(device_name: str = None):
    """
    Unmute the default Windows audio output device.
    Tries multiple methods: pycaw EndpointVolume, COM direct, etc.
    
    Args:
        device_name: Name of device (for logging only - always unmutes default)
    
    Returns:
        bool: True if successful, False otherwise
    """
    default_name = "Default Audio Device"
    
    # Method 1: Try pycaw's EndpointVolume property (simplest and most reliable)
    if pycaw_available:
        try:
            default_device = AudioUtilities.GetSpeakers()
            default_name = default_device.FriendlyName
            
            # Use EndpointVolume property (confirmed to exist)
            volume = default_device.EndpointVolume
            volume.SetMute(0, None)
            is_muted = volume.GetMute()
            if not is_muted:
                logger.info(f"Successfully unmuted default device (via EndpointVolume): {default_name}")
                print(f"Successfully unmuted default audio device: {default_name}")
                return True
            else:
                logger.warning(f"Unmute command sent but device is still muted: {default_name}")
                print(f"WARNING: Unmute command sent but device '{default_name}' is still muted")
                return False
        except Exception as e:
            logger.debug(f"Method 1 (EndpointVolume) failed: {e}")
            logger.warning(f"Could not unmute via EndpointVolume: {e}")
    
    # Method 1b: Try accessing pycaw's internal COM interface
    if pycaw_available and comtypes_available:
        try:
            default_device = AudioUtilities.GetSpeakers()
            default_name = default_device.FriendlyName
            
            # Try to access the internal COM device interface
            internal_device = None
            for attr_name in ['_device', 'device', '_interface', 'interface', '_comobj', 'comobj']:
                if hasattr(default_device, attr_name):
                    internal_device = getattr(default_device, attr_name)
                    if internal_device is not None:
                        logger.debug(f"Found internal device via attribute: {attr_name}")
                        break
            
            if internal_device is not None and ISimpleAudioVolume is not None:
                # Try to activate ISimpleAudioVolume on the internal device
                interface = internal_device.Activate(ISimpleAudioVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(ISimpleAudioVolume))
                volume.SetMute(0, None)
                is_muted = volume.GetMute()
                if not is_muted:
                    logger.info(f"Successfully unmuted default device (via internal COM): {default_name}")
                    print(f"Successfully unmuted default audio device: {default_name}")
                    return True
        except Exception as e:
            logger.debug(f"Method 1b (internal COM) failed: {e}")
    
    # Method 2: Try COM direct access
    if comtypes_available:
        try:
            volume = _get_default_device_via_com()
            
            # Unmute (0 = unmuted)
            volume.SetMute(0, None)
            
            # Verify unmute worked
            mute_state = comtypes.c_int()
            volume.GetMute(comtypes.byref(mute_state))
            is_muted = bool(mute_state.value)
            
            if not is_muted:
                logger.info(f"Successfully unmuted default device (via COM): {default_name}")
                print(f"Successfully unmuted default audio device: {default_name}")
                return True
            else:
                logger.warning(f"Unmute command sent but device is still muted: {default_name}")
                print(f"WARNING: Unmute command sent but device '{default_name}' is still muted")
                return False
        except Exception as e:
            logger.debug(f"Method 2 (COM direct) failed: {e}")
            if not pycaw_available:
                logger.error(f"All unmute methods failed: {e}", exc_info=True)
                print(f"ERROR unmuting audio device: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    # If we get here, all methods failed
    logger.error("All unmute methods failed")
    print("ERROR: Could not unmute audio device - all methods failed")
    return False


def unmute_default_output():
    """
    Unmute the default Windows audio output device.
    
    Returns:
        bool: True if successful, False otherwise
    """
    return unmute_device_by_name(None)


def get_default_output_mute_state():
    """
    Get the mute state of the default Windows audio output device.
    Tries multiple methods: pycaw EndpointVolume, COM direct, etc.
    
    Returns:
        bool: True if muted, False if unmuted, None if error
    """
    # Method 1: Try pycaw's EndpointVolume property (simplest and most reliable)
    if pycaw_available:
        try:
            default_device = AudioUtilities.GetSpeakers()
            volume = default_device.EndpointVolume
            return bool(volume.GetMute())
        except Exception as e:
            logger.debug(f"Method 1 (EndpointVolume) failed: {e}")
    
    # Method 2: Try COM direct access
    if comtypes_available:
        try:
            volume = _get_default_device_via_com()
            mute_state = comtypes.c_int()
            volume.GetMute(comtypes.byref(mute_state))
            return bool(mute_state.value)
        except Exception as e:
            logger.debug(f"Method 2 (COM direct) failed: {e}")
    
    return None


def get_default_device_name():
    """
    Get the friendly name of the default Windows audio output device.
    
    Returns:
        str: Device name, or None if error
    """
    if not pycaw_available:
        logger.debug("pycaw not available - cannot get default device name")
        return None
    
    try:
        default_device = AudioUtilities.GetSpeakers()
        return default_device.FriendlyName
    except Exception as e:
        logger.debug(f"Error getting default device name: {e}")
        return None

