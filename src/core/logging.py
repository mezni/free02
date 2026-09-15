"""Reusable logging configuration and logger helpers."""

import logging

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once, idempotently.

    Safe to call from any entrypoint (CLI, API, Streamlit); existing handlers
    are left intact so repeated calls do not stack duplicate handlers.
    """
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a child logger with sensible defaults."""
    return logging.getLogger(name)
