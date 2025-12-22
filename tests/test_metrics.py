import httpx
import pytest

from app.main import create_app
from app.shared.rate_limiter import rate_limiter
from app.shared.settings import settings


@pytest.mark.asyncio
async def test_metrics_endpoint_enabled(monkeypatch) -> None:
    await rate_limiter.reset()
    monkeypatch.setattr(settings, "metrics_enabled", True)
    monkeypatch.setattr(settings, "api_keys", [])
    monkeypatch.setattr(settings, "rate_limit_per_min", 100)

    metrics_app = create_app()
    transport = httpx.ASGITransport(app=metrics_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "http_requests_total" in response.text
