import logging
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
from utils.config import settings

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

class ColoredConsoleFormatter(logging.Formatter):
    """Colored formatter for console."""
    COLORS = {
        'DEBUG': '\033[94m', # Blue
        'INFO': '\033[92m', # Green
        'WARNING': '\033[93m', # Yellow
        'ERROR': '\033[91m', # Red
        'CRITICAL': '\033[95m' # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        msg = record.getMessage()
        return f"{color}[{timestamp}] {record.levelname} [{record.module}]: {msg}{self.RESET}"

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    # If logger already has handlers, return it to avoid duplicate logs
    if logger.handlers:
        return logger
        
    logger.setLevel(settings.LOG_LEVEL)
    logger.propagate = False

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredConsoleFormatter())
    logger.addHandler(console_handler)

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "app.log")
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)

    return logger
