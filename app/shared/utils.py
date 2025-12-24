from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from app.domain.models import ExtractionFields


def calculate_confidence(fields: "ExtractionFields", official_lookup_ok: bool = False) -> float:
    """Calculate confidence score based on extracted fields.

    Args:
        fields: The extraction fields to evaluate.
        official_lookup_ok: Whether the official GCAM lookup succeeded.

    Returns:
        A confidence score between 0.20 and 0.95.
    """
    score = 0.20
    if fields.license_number:
        score += 0.25
    if fields.status:
        score += 0.10
    if fields.issue_date:
        score += 0.10
    if fields.expiry_date:
        score += 0.10
    if fields.accounts:
        score += 0.10
    if fields.owner_name:
        score += 0.10
    if official_lookup_ok:
        score += 0.10
    return max(0.20, min(0.95, round(score, 2)))


def is_allowed_domain(hostname: str, allowed_domains: Iterable[str]) -> bool:
    """Check if a hostname is in the allowed domains list.

    Args:
        hostname: The hostname to check.
        allowed_domains: Iterable of allowed domain patterns.

    Returns:
        True if the hostname matches an allowed domain.
    """
    hostname = hostname.lower().strip(".")
    for domain in allowed_domains:
        candidate = domain.lower().strip(".")
        if hostname == candidate or hostname.endswith(f".{candidate}"):
            return True
    return False
