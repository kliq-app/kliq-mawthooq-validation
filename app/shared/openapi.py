from __future__ import annotations

from fastapi.security import APIKeyHeader


api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Optional API key. Required when API_KEYS is configured.",
)
