# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Shared constants and configuration."""

import os
import re
import datetime

DB_FILE = os.environ.get("CONNECTIONS_DB_FILE", "connections.db")
EXCLUDE_LAST_N = 25

DEBUG_LOG_FILE = "openai_raw_debug.log"

# Enable verbose OpenAI logging when env CONNECTION_DEBUG=True or CONNECTIONS_DEBUG=True
CONNECTION_DEBUG = (
    os.environ.get("CONNECTION_DEBUG", os.environ.get("CONNECTIONS_DEBUG", "False")).lower()
    in ("1","true","yes","y")
)

DEBUG_USERNAME = None

COLORS = {
    "yellow": "#f7f3a7",
    "green":  "#c9f7c3",
    "blue":   "#c7dcff",
    "purple": "#e3c7ff",
}
