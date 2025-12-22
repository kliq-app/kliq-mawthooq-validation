import httpx
import pytest

from app.api.v1 import routes
from app.domain.models import DocumentExtractionOutput, ExtractionFields, OfficialLookupResult
from app.infrastructure.fetcher import FetchResult
from app.main import app
from app.shared.rate_limiter import rate_limiter
from app.shared.settings import settings


@pytest.mark.asyncio
async def test_api_key_required(monkeypatch) -> None:
    await rate_limiter.reset()
    monkeypatch.setattr(settings, "api_keys", ["secret"]) 
    monkeypatch.setattr(settings, "rate_limit_per_min", 100)

    async def fake_fetch_content(url: str) -> FetchResult:
        return FetchResult(
            url=url,
            content_type="application/pdf",
            size_bytes=123,
            detected_type="pdf",
            warnings=[],
            content=b"%PDF-1.4 test",
        )

    async def fake_execute(self, content, detected_type, doc_type_hint, debug=None):
        return DocumentExtractionOutput(
            fields=ExtractionFields(),
            raw_fields=ExtractionFields(),
            confidence=0.2,
            warnings=[],
            official_lookup=OfficialLookupResult(
                performed=False,
                ok=False,
                status_code=None,
                match=False,
                data=None,
                error=None,
            ),
        )

    monkeypatch.setattr(routes, "fetch_content", fake_fetch_content)
    monkeypatch.setattr(routes, "use_case", type("StubUseCase", (), {"execute": fake_execute})())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/extract",
            json={"source_url": "https://example.com/license.pdf", "doc_type_hint": "auto"},
        )
        assert response.status_code == 401
        response = await client.post(
            "/v1/extract",
            json={"source_url": "https://example.com/license.pdf", "doc_type_hint": "auto"},
            headers={"x-api-key": "secret"},
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_per_ip(monkeypatch) -> None:
    await rate_limiter.reset()
    monkeypatch.setattr(settings, "api_keys", [])
    monkeypatch.setattr(settings, "rate_limit_per_min", 2)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"x-forwarded-for": "1.2.3.4"}
        response = await client.get("/health", headers=headers)
        assert response.status_code == 200
        response = await client.get("/health", headers=headers)
        assert response.status_code == 200
        response = await client.get("/health", headers=headers)
        assert response.status_code == 429
