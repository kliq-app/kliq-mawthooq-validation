from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.infrastructure.security import validate_remote_url
from app.shared.errors import AppError
from app.shared.metrics import metrics
from app.shared.settings import settings


@dataclass
class FetchResult:
    url: str
    content_type: Optional[str]
    size_bytes: int
    detected_type: str
    warnings: list[str]
    content: bytes


def _normalize_content_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.split(";")[0].strip().lower()


def _detect_type_from_magic(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if data.startswith(b"\xff\xd8\xff"):
        return "image"
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image"

    sample = data[:512].lstrip().lower()
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return "html"
    return "unknown"


def _detect_type_from_header(content_type: Optional[str]) -> str:
    if not content_type:
        return "unknown"
    if content_type == "application/pdf":
        return "pdf"
    if content_type.startswith("image/"):
        return "image"
    if content_type in {"text/html", "application/xhtml+xml"}:
        return "html"
    return "unknown"


def _validate_content_type(content_type: Optional[str]) -> Optional[str]:
    if not content_type:
        return "missing_content_type"
    if content_type in {"application/pdf", "text/html", "application/xhtml+xml"}:
        return None
    if content_type.startswith("image/"):
        return None
    return "unexpected_content_type"


async def fetch_content(url: str) -> FetchResult:
    await validate_remote_url(url, settings.allowed_domains)

    max_bytes = settings.max_download_mb * 1024 * 1024
    warnings: list[str] = []

    timeout = httpx.Timeout(settings.request_timeout_sec)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, max_redirects=3, limits=limits) as client:
        try:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type_header = _normalize_content_type(response.headers.get("content-type"))
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit():
                    if int(content_length) > max_bytes:
                        raise AppError("payload_too_large", "Remote content exceeds size limit", 413)

                content_type_warning = _validate_content_type(content_type_header)
                if content_type_warning:
                    warnings.append(content_type_warning)

                buffer = bytearray()
                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > max_bytes:
                        raise AppError("payload_too_large", "Remote content exceeds size limit", 413)

                data = bytes(buffer)
        except httpx.HTTPError as exc:
            raise AppError("fetch_failed", f"Failed to download content: {exc}", 502) from exc

    magic_type = _detect_type_from_magic(data)
    header_type = _detect_type_from_header(content_type_header)
    detected_type = magic_type if magic_type != "unknown" else header_type

    if header_type != "unknown" and magic_type != "unknown" and header_type != magic_type:
        warnings.append("content_type_mismatch")

    metrics.observe_download(len(data), detected_type)

    return FetchResult(
        url=url,
        content_type=content_type_header,
        size_bytes=len(data),
        detected_type=detected_type,
        warnings=warnings,
        content=data,
    )
