import httpx
import pytest

from app.api.v1 import routes
from app.application.use_cases.extract_document import build_default_use_case
from app.domain.models import (
    AccountHandle,
    DebugInfo,
    DocumentExtractionOutput,
    ExtractionFields,
    OfficialData,
    OfficialLookupResult,
)
from app.infrastructure.fetcher import FetchResult
from app.main import app
from app.shared.settings import settings


@pytest.fixture(autouse=True)
def _disable_api_keys(monkeypatch):
    monkeypatch.setattr(settings, "api_keys", [])
    monkeypatch.setattr(settings, "rate_limit_per_min", 100)


@pytest.mark.asyncio
async def test_extract_stub(monkeypatch) -> None:
    async def fake_fetch_content(url: str) -> FetchResult:
        return FetchResult(
            url=url,
            content_type="application/pdf",
            size_bytes=123,
            detected_type="pdf",
            warnings=[],
            content=b"%PDF-1.4 test",
        )

    monkeypatch.setattr(routes, "fetch_content", fake_fetch_content)
    async def fake_execute(self, content, detected_type, doc_type_hint, debug=None):
        return DocumentExtractionOutput(
            fields=ExtractionFields(license_number="12345"),
            raw_fields=ExtractionFields(license_number="12345"),
            confidence=0.8,
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

    monkeypatch.setattr(routes, "use_case", type("StubUseCase", (), {"execute": fake_execute})())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/extract",
            json={"source_url": "https://example.com/license.pdf", "doc_type_hint": "auto"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["doc_type"] == "pdf"
    assert payload["source"]["url"] == "https://example.com/license.pdf"
    assert payload["fields"]["license_number"] == "12345"
    assert payload["confidence"] == 0.8
    assert payload["official_lookup"]["performed"] is False
    assert payload["official_lookup"]["status_code"] is None
    assert "raw_extraction" not in payload
    assert "debug" not in payload
    assert "data" not in payload["official_lookup"]
    assert "error" not in payload["official_lookup"]


@pytest.mark.asyncio
async def test_extract_debug_includes_fields(monkeypatch) -> None:
    async def fake_fetch_content(url: str) -> FetchResult:
        return FetchResult(
            url=url,
            content_type="application/pdf",
            size_bytes=123,
            detected_type="pdf",
            warnings=[],
            content=b"%PDF-1.4 test",
        )

    monkeypatch.setattr(routes, "fetch_content", fake_fetch_content)

    async def fake_execute(self, content, detected_type, doc_type_hint, debug=None):
        return DocumentExtractionOutput(
                fields=ExtractionFields(
                    license_number="12345",
                    accounts=[AccountHandle(platform="twitter", handle="@example")],
                ),
                raw_fields=ExtractionFields(
                    license_number="12345",
                    accounts=[AccountHandle(platform="twitter", handle="@example")],
                ),
            confidence=0.8,
            warnings=[],
            official_lookup=OfficialLookupResult(
                performed=True,
                ok=True,
                status_code=200,
                match=True,
                    data=OfficialData(
                        license_number="12345",
                        owner_name="Test Owner",
                        accounts=[AccountHandle(platform="twitter", handle="@example")],
                    ),
                error=None,
            ),
            debug=DebugInfo(
                pdf_text_len=120,
                ocr_attempted_pages=1,
                renderer_used="pymupdf",
                ocr_engine_used="tesseract",
                tesseract_available=True,
                tesseract_langs_contains_ara=True,
            ),
        )

    monkeypatch.setattr(routes, "use_case", type("StubUseCase", (), {"execute": fake_execute})())

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/extract?debug=true",
            json={"source_url": "https://example.com/license.pdf", "doc_type_hint": "auto"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_extraction"]["license_number"] == "12345"
    assert payload["official_lookup"]["data"]["license_number"] == "12345"
    assert payload["debug"]["pdf_text_len"] == 120


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "بطاقة موثوق\nMawthooq_87_Name / الاسم زايد ساير زايد الشهري\nموثوق",
            "زايد ساير زايد الشهري",
        ),
        (
            "الهيئة العامة لتنظيم الإعلام\nاسم المالك: موسى ابراهيم موسى آل جوير\nترخيص إعلامي",
            "موسى ابراهيم موسى آل جوير",
        ),
    ],
)
async def test_extract_owner_name_from_text(monkeypatch, text, expected) -> None:
    async def fake_fetch_content(url: str) -> FetchResult:
        return FetchResult(
            url=url,
            content_type="application/pdf",
            size_bytes=123,
            detected_type="pdf",
            warnings=[],
            content=b"%PDF-1.4 test",
        )

    monkeypatch.setattr(routes, "fetch_content", fake_fetch_content)
    use_case = build_default_use_case()
    monkeypatch.setattr(routes, "use_case", use_case)
    monkeypatch.setattr(use_case.pdf_text_extractor, "extract", lambda content: text)
    monkeypatch.setattr(settings, "gcam_lookup_enabled", False)
    monkeypatch.setattr(settings, "min_text_length", 0)
    monkeypatch.setattr(settings, "min_arabic_ratio", 0.0)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/extract",
            json={"source_url": "https://example.com/license.pdf", "doc_type_hint": "auto"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["fields"]["owner_name"] == expected
