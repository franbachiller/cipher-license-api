"""
Logging configuration with file rotation.

This module provides structured logging with:
- Timestamp, log level, and message formatting
- Rotating file handler (10MB max size, 5 backups)
- Both file and console output
- Configuration via environment variables
"""

import logging
from logging.handlers import RotatingFileHandler
import os

from ..config import Config


def setup_logging(app=None) -> logging.Logger:
    """
    Configure application logging with rotating file handler.
    
    Sets up structured logging with:
    - Timestamp in ISO 8601 format
    - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - Logger name
    - Message content
    
    Configures two handlers:
    - RotatingFileHandler: Writes to file with 10MB max size and 5 backups
    - StreamHandler: Writes to console for real-time monitoring
    
    Configuration is loaded from environment variables:
    - LOG_LEVEL: Logging level (default: INFO)
    - LOG_FILE: Log file path (default: api_server.log)
    - LOG_MAX_BYTES: Max file size before rotation (default: 10MB)
    - LOG_BACKUP_COUNT: Number of backup files to keep (default: 5)
    
    Args:
        app: Flask application instance (optional, for future integration)
    
    Returns:
        Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger('cipher_api')
    
    # Set log level from configuration
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Prevent duplicate handlers if setup_logging is called multiple times
    if logger.handlers:
        return logger
    
    # Create structured log formatter
    # Format: 2024-01-15 10:30:45,123 - cipher_api - INFO - Authentication successful
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set up rotating file handler
    # Rotates when file reaches LOG_MAX_BYTES (default 10MB)
    # Keeps LOG_BACKUP_COUNT backup files (default 5)
    try:
        # Ensure log directory exists
        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            filename=Config.LOG_FILE,
            maxBytes=Config.LOG_MAX_BYTES,
            backupCount=Config.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        # If file handler fails, log to console only
        print(f"WARNING: Failed to create log file handler: {e}")
        print(f"Logging to console only")
    
    # Set up console handler for real-time monitoring
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Log initial configuration
    logger.info(f"Logging configured: level={Config.LOG_LEVEL}, file={Config.LOG_FILE}")
    logger.info(f"File rotation: max_bytes={Config.LOG_MAX_BYTES}, backup_count={Config.LOG_BACKUP_COUNT}")
    
    return logger


def get_logger(name: str = 'cipher_api') -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Logger name (typically __name__ from the calling module)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
