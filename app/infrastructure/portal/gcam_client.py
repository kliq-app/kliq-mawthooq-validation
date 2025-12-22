from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.shared.settings import settings


@dataclass
class GcamLookupResult:
    ok: bool
    status_code: Optional[int]
    html_text: Optional[str]
    error: Optional[str]


def _is_allowed_domain(hostname: str, allowed_domains: list[str]) -> bool:
    hostname = hostname.lower().strip(".")
    for domain in allowed_domains:
        candidate = domain.lower().strip(".")
        if hostname == candidate or hostname.endswith(f".{candidate}"):
            return True
    return False


def _lookup_url(license_number: str) -> str:
    base = settings.gcam_base_url.rstrip("/")
    return f"{base}/gcam-licenses/gcam-celebrity-check/{license_number}"


async def fetch_gcam_license(license_number: str) -> GcamLookupResult:
    url = _lookup_url(license_number)
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if settings.allowed_domains and not _is_allowed_domain(hostname, settings.allowed_domains):
        return GcamLookupResult(
            ok=False,
            status_code=None,
            html_text=None,
            error="domain_not_allowed",
        )

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Referer": settings.gcam_base_url,
    }

    timeout = httpx.Timeout(settings.gcam_lookup_timeout_sec)
    limits = httpx.Limits(max_keepalive_connections=2, max_connections=5)
    retries = max(0, settings.gcam_lookup_retry_count)

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, max_redirects=3, limits=limits) as client:
        for attempt in range(retries + 1):
            try:
                response = await client.get(url, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < retries:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return GcamLookupResult(ok=False, status_code=None, html_text=None, error=str(exc))

            status = response.status_code
            if 500 <= status <= 599 and attempt < retries:
                await asyncio.sleep(0.5 * (2**attempt))
                continue

            if status == 200:
                return GcamLookupResult(
                    ok=True,
                    status_code=status,
                    html_text=response.text,
                    error=None,
                )

            return GcamLookupResult(
                ok=False,
                status_code=status,
                html_text=response.text,
                error=f"http_{status}",
            )

    return GcamLookupResult(ok=False, status_code=None, html_text=None, error="unknown")
