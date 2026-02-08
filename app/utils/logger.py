"""Logging configuration helper."""
import logging
from logging import Logger
from app.config.settings import Settings

def configure_logging(settings: Settings) -> None:
    """Configure root logging for the app."""
    level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

def get_logger(name: str) -> Logger:
    """Get a named logger."""
    return logging.getLogger(name)
