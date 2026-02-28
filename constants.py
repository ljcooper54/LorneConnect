# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Shared constants and configuration."""

import os
import re
import datetime

DB_FILE = os.environ.get("CONNECTIONS_DB_FILE", "connections.db")
EXCLUDE_LAST_N = 25

DEBUG_LOG_FILE = "openai_raw_debug.log"

def _env_flag(name: str, default: bool = False) -> bool:
    """Return boolean from environment variable."""
    val = os.environ.get(name)
    if val is None:
        return default
    val = val.strip().lower()
    return val not in ("0", "false", "no", "off", "")

CONNECTION_DEBUG = _env_flag("DEBUG", False)

DEBUG_USERNAME = None

COLORS = {
    "yellow": "#f7f3a7",
    "green":  "#c9f7c3",
    "blue":   "#c7dcff",
    "purple": "#e3c7ff",
}
