from __future__ import annotations

import re
from typing import Any


_SENSITIVE_KEYS = {"id_number", "owner_name"}


def redact_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        redacted: dict[str, Any] = {}
        for key, value in payload.items():
            key_lower = str(key).lower()
            if key_lower in _SENSITIVE_KEYS:
                redacted[key] = _mask_value(key_lower, value)
            else:
                redacted[key] = redact_payload(value)
        return redacted
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    return payload


def _mask_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if key == "id_number":
        return _mask_id(text)
    if key == "owner_name":
        return _mask_name(text)
    return "***"


def _mask_id(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not digits:
        return "***"
    keep = digits[-4:]
    masked = "*" * max(0, len(digits) - len(keep)) + keep
    return masked


def _mask_name(value: str) -> str:
    value = value.strip()
    if not value:
        return "***"
    first_char = value[0]
    return f"{first_char}***"
