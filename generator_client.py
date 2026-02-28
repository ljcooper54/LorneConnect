# File: App/generator_client.py | Created/Modified: 2026-02-26
# Copyright 2025 H2so4 Consulting LLC
"""OpenAI JSON client wrapper.

Enhancement:
- Adds timestamp + module name to DEBUG logging.
- Logs every OpenAI call, response size, and JSON parsing issues.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from openai import OpenAI


# This JSON client wraps OpenAI structured calls. (Start)
class OpenAIJSONClient:
    """Minimal JSON client wrapper around OpenAI."""

    # This initializes the OpenAI client. (Start)
    def __init__(self, model: str | None = None):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._module = __name__.split(".")[-1]
    # end def __init__  # __init__

    # This returns True if DEBUG env is enabled. (Start)
    def _debug_enabled(self) -> bool:
        v = os.environ.get("DEBUG", "")
        return v.strip().casefold() in {"1", "true", "yes", "y", "on"}
    # end def _debug_enabled  # _debug_enabled

    # This returns a timestamped debug prefix. (Start)
    def _dbg_prefix(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"[{ts}][{self._module}][DEBUG]"
    # end def _dbg_prefix  # _dbg_prefix

    # This prints debug message if enabled. (Start)
    def _dbg(self, msg: str) -> None:
        if self._debug_enabled():
            print(f"{self._dbg_prefix()} {msg}")
    # end def _dbg  # _dbg

    # This performs a JSON call to OpenAI and parses the result. (Start)
    def call_json(self, prompt: str, temperature: float = 0.3) -> dict:
        self._dbg(
            f"OpenAI call model='{self.model}' temp={temperature} prompt_chars={len(prompt)}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.choices[0].message.content or ""

        self._dbg(f"OpenAI response chars={len(content)}")

        try:
            parsed = json.loads(content)
            return parsed
        except Exception as e:
            snippet = content[:500].replace("\n", "\\n")
            self._dbg(f"JSON parse failure: {e}")
            self._dbg(f"Response snippet: {snippet}")
            raise RuntimeError(f"OpenAI returned invalid JSON: {e}")
        # end try/except
    # end def call_json  # call_json

# end class OpenAIJSONClient  # OpenAIJSONClient
