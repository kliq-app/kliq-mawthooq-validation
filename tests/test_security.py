import pytest

from app.infrastructure.security import validate_remote_url
from app.shared.errors import AppError


@pytest.mark.asyncio
async def test_block_private_ip() -> None:
    with pytest.raises(AppError) as exc_info:
        await validate_remote_url("http://127.0.0.1/resource", [])
    assert exc_info.value.code == "ssrf_blocked"


@pytest.mark.asyncio
async def test_block_invalid_scheme() -> None:
    with pytest.raises(AppError) as exc_info:
        await validate_remote_url("file:///etc/passwd", [])
    assert exc_info.value.code == "invalid_url"


@pytest.mark.asyncio
async def test_block_disallowed_domain() -> None:
    with pytest.raises(AppError) as exc_info:
        await validate_remote_url("https://example.com/resource", ["allowed.com"])
    assert exc_info.value.code == "domain_not_allowed"
