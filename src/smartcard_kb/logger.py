"""Centralized logging configuration using Loguru"""

import sys
from loguru import logger

# Remove default handler and configure custom format
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
    enqueue=True,
)

__all__ = ["logger"]
