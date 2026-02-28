# File: App/app_env.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""Environment loading utilities for the app."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


# This loads .env from the project root and enforces OPENAI_API_KEY. (Start)
def load_env_and_require_openai_key() -> None:
    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not found. Ensure .env exists in project root.")
    # end if
# end def load_env_and_require_openai_key  # load_env_and_require_openai_key
