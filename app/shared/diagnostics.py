from __future__ import annotations

import re


def format_exception_warning(prefix: str, exc: Exception) -> str:
    message = str(exc).replace("\r", " ").replace("\n", " ")
    message = re.sub(r"\s+", " ", message).strip()
    if not message:
        message = "unknown"
    if len(message) > 120:
        message = message[:120]
    return f"{prefix}:{exc.__class__.__name__}:{message}"
