import pytest

from app.application.use_cases.extract_document import ExtractDocumentUseCase, gcam_circuit_breaker
from app.infrastructure.extractors.strategies import AutoExtractor, GcamPdfExtractor, MawthooqCardExtractor
from app.infrastructure.portal.gcam_client import GcamLookupResult
from app.shared.settings import settings


class StubPdfTextExtractor:
    def extract(self, data: bytes) -> str:
        return "ترخيص إعلامي\nرقم الرخصة 12345"


class StubPdfRenderer:
    def render_pages(self, data: bytes, max_pages: int = 2):
        return []


class StubOcrEngine:
    def extract_text(self, images) -> str:
        return ""


@pytest.mark.asyncio
async def test_gcam_circuit_breaker_skips_lookup(monkeypatch) -> None:
    await gcam_circuit_breaker.configure(2, 60)
    monkeypatch.setattr(settings, "gcam_lookup_enabled", True)
    monkeypatch.setattr(settings, "ocr_enabled", False)
    monkeypatch.setattr(settings, "min_text_length", 0)
    monkeypatch.setattr(settings, "min_arabic_ratio", 0.0)

    calls = {"count": 0}

    async def fake_fetch(license_number: str) -> GcamLookupResult:
        calls["count"] += 1
        return GcamLookupResult(ok=False, status_code=503, html_text=None, error="http_503")

    monkeypatch.setattr(
        "app.application.use_cases.extract_document.fetch_gcam_license",
        fake_fetch,
    )

    use_case = ExtractDocumentUseCase(
        pdf_text_extractor=StubPdfTextExtractor(),
        pdf_renderer=StubPdfRenderer(),
        ocr_engine=StubOcrEngine(),
        auto_extractor=AutoExtractor([GcamPdfExtractor(), MawthooqCardExtractor()]),
    )

    await use_case.execute(b"%PDF", "pdf", "auto")
    await use_case.execute(b"%PDF", "pdf", "auto")
    result = await use_case.execute(b"%PDF", "pdf", "auto")

    assert calls["count"] == 2
    assert "GCAM_LOOKUP_CIRCUIT_OPEN" in result.warnings
