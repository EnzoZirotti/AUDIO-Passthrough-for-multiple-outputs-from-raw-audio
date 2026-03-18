"""
Structured logging for audio player application.
Provides consistent logging with levels, timestamps, and optional file output.
"""

import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "BluetoothStreamer", log_file: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a structured logger for the application.
    
    Args:
        name: Logger name
        log_file: Optional path to log file (if None, only console logging)
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger
    
    # Create formatter with timestamp, level, and message
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (always)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        try:
            # Ensure log directory exists
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # If file logging fails, continue with console only
            logger.warning(f"Could not set up file logging: {e}")
    
    return logger


# Default logger instance
_default_logger = None


def get_logger(name: str = "BluetoothStreamer") -> logging.Logger:
    """
    Get or create the default logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    global _default_logger
    if _default_logger is None:
        # Set up default logger with optional file logging
        log_dir = Path.home() / ".bluetoothstreamer" / "logs"
        log_file = log_dir / f"bluetoothstreamer_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Only enable file logging if directory is writable
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            _default_logger = setup_logger(name, str(log_file))
        except Exception:
            # Fall back to console-only logging
            _default_logger = setup_logger(name, None)
    
    return _default_logger

