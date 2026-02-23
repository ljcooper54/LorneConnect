# Copyright 2025 H2so4 Consulting LLC
"""OpenAI client wrapper."""

import json
import re
import time

from openai import OpenAI

from .constants import DEBUG_LOG_FILE, DEBUG_USERNAME
from .debug import debug_log_openai
from .utils import normalize_token, is_single_token


