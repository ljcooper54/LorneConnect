# File: App/openai_client.py | Created/Modified: 2026-02-25
# Copyright 2025 H2so4 Consulting LLC
"""OpenAI client wrapper for category seeding.

This module only handles the category-seeding call (new category -> 100 words).
All normal puzzle generation should be local DB-driven and MUST NOT call OpenAI.
"""

from __future__ import annotations

import os
from typing import Iterable

from openai import OpenAI


# This OpenAIClient wraps the OpenAI SDK with a narrow API. (Start)
class OpenAIClient:
    """Thin wrapper around OpenAI for category seeding."""

    # This initializes the OpenAI SDK client and checks for API key. (Start)
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        # end if
        self._client = OpenAI(api_key=api_key)
    # end def __init__  # __init__

    # This asks OpenAI for additional unique seed items for a category as strict JSON. (Start)
    def generate_category_seed(self, category: str, exclude_words: list[str], target_count: int) -> str:
        """
        Returns a JSON *string* with schema:
        {
          "category": "<string>",
          "items": [{"word":"...", "obscurity":1..4}, ...]
        }
        """
        # Keep request sizes sane; ask for up to 100 at a time, accumulate via retries.
        n = max(20, min(int(target_count), 100))

        # We tell the model it is allowed to return FEWER than n if it cannot find unique terms.
        # The seeder will retry and/or accept MIN_ACCEPTABLE.
        exclude_preview = ", ".join(exclude_words[:100])

        prompt = f"""
You are generating seed vocabulary for a word-grouping game.

Category: "{category}"

Goal: Produce up to {n} UNIQUE words/phrases strongly associated with the category.
Each item must include obscurity (1=very common, 4=very obscure).

Hard constraints:
- Output MUST be valid JSON (no markdown, no commentary).
- Root object: keys "category" and "items".
- "items" is an array of objects: {{"word": <string>, "obscurity": <int 1-4>}}.
- DO NOT repeat any "word" inside this response.
- DO NOT include any word that matches (case/whitespace-insensitive) any of these excluded tokens:
  [{exclude_preview}]
- Prefer domain-specific terms. Avoid generic fillers (e.g., "salad", "pasta") unless genuinely category-specific.
- If you cannot find {n} unique items, return fewer rather than repeating.

Return ONLY the JSON object.
""".strip()

        # Use a deterministic temperature to reduce weirdness.
        resp = self._client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        text = resp.choices[0].message.content or ""
        return text
    

    # This explains a word in the context of a category in <=50 words, with up to 2 hyperlinks. (Start)
    def explain_word(self, category: str, word: str) -> str:
        """Return a short explanation (<=50 words) and optional 1-2 hyperlinks."""
        cat = (category or "").strip()
        w = (word or "").strip()

        prompt = (
            "Explain the word in the context of the category.\n"
            f"Category: {cat}\n"
            f"Word: {w}\n\n"
            "Requirements:\n"
            "- Max 50 words.\n"
            "- If appropriate, include up to 2 full https:// hyperlinks (each on its own line).\n"
            "- Plain text only.\n"
        )

        resp = self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise explainer. Keep within limits."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

        text = (resp.choices[0].message.content or "").strip()
        return text
    # end def explain_word  # explain_word
# end def generate_category_seed  # generate_category_seed

# end class OpenAIClient  # OpenAIClient
