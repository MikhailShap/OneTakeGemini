"""
Logging module for OneTake application.
Provides file and console logging with rotation.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from src.utils.paths import get_logs_dir


def setup_logger(name: str = "onetake", level: int = logging.DEBUG) -> logging.Logger:
    """
    Sets up and returns a logger with file and console handlers.

    Args:
        name: Logger name
        level: Logging level (default DEBUG for troubleshooting)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Formatter with timestamp, level, module and message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation (5 files, 5MB each)
    try:
        logs_dir = get_logs_dir()
        log_file = os.path.join(logs_dir, "onetake.log")

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # If file logging fails, continue with console only
        print(f"Warning: Could not setup file logging: {e}")

    # Console handler (for development/debugging)
    # Only add if not frozen (running as exe) to avoid console window issues
    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def get_logger(module_name: str = None) -> logging.Logger:
    """
    Gets a logger for a specific module.

    Args:
        module_name: Name of the module (e.g., 'recorder', 'camera_manager')

    Returns:
        Logger instance
    """
    if module_name:
        return logging.getLogger(f"onetake.{module_name}")
    return logging.getLogger("onetake")


# Ленивая инициализация логгера для ускорения запуска приложения
_main_logger = None


def _get_logger():
    """Получить или создать логгер (ленивая инициализация)."""
    global _main_logger
    if _main_logger is None:
        _main_logger = setup_logger()
    return _main_logger


def debug(msg: str, *args, **kwargs):
    """Log debug message."""
    _get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs):
    """Log info message."""
    _get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs):
    """Log warning message."""
    _get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs):
    """Log error message."""
    _get_logger().error(msg, *args, **kwargs)


def exception(msg: str, *args, **kwargs):
    """Log exception with traceback."""
    _get_logger().exception(msg, *args, **kwargs)
