"""Centralized logging configuration.

A single place to configure log formatting / level so every module
in the pipeline shares the same conventions.
"""
from __future__ import annotations

import logging
import os
import sys
from logging import Logger

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root() -> None:
    """Configure the root logger once per process."""
    global _configured
    if _configured:
        return

    level_name = os.getenv("BULK_INTEL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    _configured = True


def get_logger(name: str) -> Logger:
    """Return a module-level logger with shared configuration.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        Configured ``logging.Logger`` instance.
    """
    _configure_root()
    return logging.getLogger(name)
