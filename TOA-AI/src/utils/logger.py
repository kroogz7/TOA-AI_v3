"""
TOA-AI Logger Utility
Provides consistent logging throughout the application
"""

import sys
import os
from pathlib import Path
from loguru import logger
import time

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import LOGGING, ROOT_DIR

# Remove default logger
logger.remove()

# Add console logger
logger.add(
    sys.stdout,
    level=LOGGING["log_level"],
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Add file logger if enabled
if LOGGING["log_to_file"]:
    log_file = LOGGING.get("log_file", ROOT_DIR / "logs" / "toa_ai.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logger.add(
        log_file,
        rotation="10 MB",
        retention="1 week",
        level=LOGGING["log_level"],
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )

def get_logger(name):
    """Get a logger with the given name"""
    return logger.bind(name=name)

# Create a function for timing operations
def timer(func):
    """Decorator to time function execution"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} completed in {end_time - start_time:.2f} seconds")
        return result
    return wrapper 