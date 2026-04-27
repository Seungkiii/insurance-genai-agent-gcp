"""Logging helper placeholders."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(name)
