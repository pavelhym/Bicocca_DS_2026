import json
import logging
import os
import sys

from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs logs in JSON format."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)


class ReadableFormatter(logging.Formatter):
    """Human-readable formatter for console output."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def initialize_logger(
    log_name: str = "app",
    log_level: int = logging.INFO,
    log_dir: str = "logs",
    console_output: bool = True,
    json_format: bool = True,
) -> logging.Logger:
    """
    Initialize and configure a logger with JSON file output and optional console output.

    Args:
        log_name: Name prefix for log files (e.g., "chatbot", "api", "worker")
        log_level: Logging level (default: logging.INFO)
        log_dir: Directory to save log files (default: "Log/logs")
        console_output: Whether to output logs to console (default: True)
        json_format: Whether to use JSON format for file logs (default: True)

    Returns:
        Configured logger instance

    Example:
        >>> logger = initialize_logger("chatbot")
        >>> logger.info("Application started")
    """
    # Ensure the log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Create logger with the provided name
    logger_name = f"{log_name}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Remove existing handlers to prevent duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create log file path with name prefix
    log_filename = f"{log_name}_{datetime.now().strftime('%Y-%m-%d')}.log"
    log_file = os.path.join(log_dir, log_filename)

    # Create file handler with rotation
    file_handler = TimedRotatingFileHandler(
        log_file, when="midnight", interval=1, backupCount=30, encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_handler.setLevel(log_level)

    # Set formatter for file handler
    if json_format:
        file_formatter = JSONFormatter()
    else:
        file_formatter = ReadableFormatter()
    file_handler.setFormatter(file_formatter)

    # Add file handler to logger
    logger.addHandler(file_handler)

    # Create console handler if requested
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = ReadableFormatter()
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Log initialization
    logger.info(f"Logger '{logger_name}' initialized with log file: {log_file}")

    return logger


# Default logger initialization (for backward compatibility)
def get_default_logger() -> logging.Logger:
    """Get or create the default logger."""
    return initialize_logger(log_name="app", console_output=True)
