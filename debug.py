# Copyright 2025 H2so4 Consulting LLC
from __future__ import annotations
"""Debug logging."""

import json
import re
import datetime
from .constants import CONNECTION_DEBUG

def _debug_log_filename(username: str) -> str:
    # Build per-user per-day debug log filename.
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", username or "unknown")
    return f"Connection_{safe}_{date_str}.log"
# end def _debug_log_filename


def debug_log_openai(username: str, status: str, messages, raw_content: str, error: str = ""):
    # Append OpenAI call details to per-user log if CONNECTION_DEBUG is enabled.
    if not CONNECTION_DEBUG:
        return
    try:
        fname = _debug_log_filename(username)
        with open(fname, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 90 + "\n")
            f.write(f"TIME: {datetime.datetime.now().isoformat(sep=' ', timespec='seconds')}\n")
            f.write(f"STATUS: {status}\n")
            if error:
                f.write(f"ERROR: {error}\n")
            f.write("MESSAGES:\n")
            f.write(json.dumps(messages, indent=2))
            f.write("\nRAW_RESPONSE:\n")
            f.write((raw_content or "") + "\n")
    except Exception:
        pass
# end def debug_log_openai
