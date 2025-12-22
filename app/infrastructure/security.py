from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse

from app.shared.errors import AppError


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return False
    if ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return False
    return True


def _is_allowed_domain(hostname: str, allowed_domains: Iterable[str]) -> bool:
    hostname = hostname.lower().strip(".")
    for domain in allowed_domains:
        candidate = domain.lower().strip(".")
        if hostname == candidate or hostname.endswith(f".{candidate}"):
            return True
    return False


async def _resolve_host(hostname: str) -> list[ipaddress._BaseAddress]:
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(hostname, None, type=0, proto=0, flags=0)
    ips: list[ipaddress._BaseAddress] = []
    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            ip_str = sockaddr[0]
        else:
            ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        ips.append(ip)
    return ips


async def validate_remote_url(url: str, allowed_domains: list[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise AppError("invalid_url", "Only http/https URLs are allowed", 400)

    hostname = parsed.hostname
    if not hostname:
        raise AppError("invalid_url", "URL hostname is missing", 400)

    if allowed_domains and not _is_allowed_domain(hostname, allowed_domains):
        raise AppError("domain_not_allowed", "URL domain is not allowed", 403)

    try:
        ip = ipaddress.ip_address(hostname)
        if not _is_public_ip(ip):
            raise AppError("ssrf_blocked", "URL resolved to a private address", 403)
        return
    except ValueError:
        pass

    resolved_ips = await _resolve_host(hostname)
    if not resolved_ips:
        raise AppError("dns_failed", "Could not resolve URL hostname", 400)

    for ip in resolved_ips:
        if not _is_public_ip(ip):
            raise AppError("ssrf_blocked", "URL resolved to a private address", 403)
