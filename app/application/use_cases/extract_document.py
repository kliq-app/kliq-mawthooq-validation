from __future__ import annotations

import io
import unicodedata

from app.domain.models import (
    AccountHandle,
    DebugInfo,
    DocumentExtractionOutput,
    ExtractionFields,
    OfficialData,
    OfficialLookupResult,
)
from app.infrastructure.extractors.strategies import AutoExtractor, GcamPdfExtractor, MawthooqCardExtractor
from app.infrastructure.ocr.base import OcrEngine
from app.infrastructure.ocr.tesseract import TesseractOcrEngine
from app.infrastructure.portal.gcam_client import fetch_gcam_license
from app.infrastructure.portal.gcam_parser import parse_gcam_html
from app.infrastructure.pdf.renderer import PdfRenderer
from app.infrastructure.pdf.text_extractor import PdfTextExtractor
from app.infrastructure.parsing.fields import (
    arabic_ratio,
    extract_owner_name,
    has_pdf_text_signal,
    normalize_text,
    parse_account_entry,
)
from app.shared.circuit_breaker import CircuitBreaker
from app.shared.dependencies import tesseract_available, tesseract_has_ara
from app.shared.diagnostics import format_exception_warning
from app.shared.metrics import metrics
from app.shared.settings import settings

gcam_circuit_breaker = CircuitBreaker(
    settings.gcam_cb_failure_threshold,
    settings.gcam_cb_reset_sec,
)


class ExtractDocumentUseCase:
    def __init__(
        self,
        pdf_text_extractor: PdfTextExtractor,
        pdf_renderer: PdfRenderer,
        ocr_engine: OcrEngine,
        auto_extractor: AutoExtractor,
    ) -> None:
        self.pdf_text_extractor = pdf_text_extractor
        self.pdf_renderer = pdf_renderer
        self.ocr_engine = ocr_engine
        self.auto_extractor = auto_extractor

    async def execute(
        self,
        content: bytes,
        detected_type: str,
        doc_type_hint: str,
        debug: bool | None = None,
    ) -> DocumentExtractionOutput:
        warnings: list[str] = []
        text = ""
        pdf_text_len = 0
        ocr_attempted_pages = 0
        renderer_used: str | None = None
        ocr_engine_used: str | None = None
        debug_enabled = settings.extract_debug if debug is None else debug
        ocr_images = []

        if detected_type == "pdf":
            try:
                text = self.pdf_text_extractor.extract(content)
                text = unicodedata.normalize("NFKC", text)
            except Exception:
                warnings.append("pdf_text_failed")
                text = ""

            normalized = normalize_text(text)
            pdf_text_len = len(normalized)
            ratio = arabic_ratio(normalized)
            has_signal = has_pdf_text_signal(normalized)
            if (ratio < settings.min_arabic_ratio or len(normalized) < settings.min_text_length) and not has_signal:
                warnings.append("pdf_text_insufficient")
                if settings.ocr_enabled:
                    renderer_used = "pymupdf"
                    ocr_engine_used = "tesseract"
                    ocr_attempted_pages = settings.max_ocr_pages
                    try:
                        images = self.pdf_renderer.render_pages(content, max_pages=settings.max_ocr_pages)
                    except Exception as exc:
                        warnings.append(format_exception_warning("pdf_render_failed", exc))
                        images = []

                    if images:
                        ocr_attempted_pages = len(images)
                        ocr_images = images
                        try:
                            start = metrics.now()
                            text = self.ocr_engine.extract_text(images)
                            metrics.observe_ocr("pdf", metrics.now() - start)
                            warnings.append("ocr_used")
                        except Exception as exc:
                            warnings.append(format_exception_warning("ocr_failed", exc))
                else:
                    warnings.append("ocr_disabled")
        elif detected_type == "image":
            if settings.ocr_enabled:
                try:
                    from PIL import Image

                    image = Image.open(io.BytesIO(content)).convert("RGB")
                    ocr_engine_used = "tesseract"
                    ocr_images = [image]
                    start = metrics.now()
                    text = self.ocr_engine.extract_text([image])
                    metrics.observe_ocr("image", metrics.now() - start)
                    warnings.append("ocr_used")
                except Exception as exc:
                    warnings.append(format_exception_warning("ocr_failed", exc))
            else:
                warnings.append("ocr_disabled")
        else:
            warnings.append("unsupported_doc_type")
            return DocumentExtractionOutput(
                fields=ExtractionFields(),
                raw_fields=ExtractionFields(),
                confidence=_calculate_confidence(ExtractionFields(), False),
                warnings=warnings,
                official_lookup=OfficialLookupResult(
                    performed=False,
                    ok=False,
                    status_code=None,
                    match=False,
                    data=None,
                    error=None,
                ),
                debug=_build_debug(
                    pdf_text_len,
                    ocr_attempted_pages,
                    renderer_used,
                    ocr_engine_used,
                    debug_enabled,
                ),
            )

        if not text.strip():
            warnings.append("empty_text")

        preferred = None
        if doc_type_hint in {"gcam_pdf", "gcam_page"}:
            preferred = "gcam_pdf"
        elif doc_type_hint == "mawthooq_card":
            preferred = "mawthooq_card"

        result = self.auto_extractor.extract(text, preferred=preferred)
        warnings = warnings + result.warnings

        raw_fields = result.fields
        if not raw_fields.owner_name and ocr_images and _should_try_gcam_owner_roi(preferred, result.warnings):
            owner_name = _extract_owner_name_from_gcam_roi(self.ocr_engine, ocr_images)
            if owner_name:
                raw_fields.owner_name = owner_name
        merged_fields = raw_fields
        official_lookup = OfficialLookupResult(
            performed=False,
            ok=False,
            status_code=None,
            match=False,
            data=None,
            error=None,
        )

        if raw_fields.license_number and settings.gcam_lookup_enabled:
            if not await gcam_circuit_breaker.allow():
                warnings.append("GCAM_LOOKUP_CIRCUIT_OPEN")
                metrics.observe_gcam_lookup("circuit_open", 0.0)
                official_lookup = OfficialLookupResult(
                    performed=False,
                    ok=False,
                    status_code=None,
                    match=False,
                    data=None,
                    error="circuit_open",
                )
            else:
                start = metrics.now()
                official_lookup = await _lookup_gcam(raw_fields.license_number)
                duration = metrics.now() - start
                if official_lookup.ok:
                    await gcam_circuit_breaker.record_success()
                    metrics.observe_gcam_lookup("success", duration)
                else:
                    await gcam_circuit_breaker.record_failure()
                    metrics.observe_gcam_lookup("failure", duration)
                    if official_lookup.error:
                        warnings.append(f"GCAM_LOOKUP_FAILED:{official_lookup.error}")

            if official_lookup.ok and official_lookup.data:
                merged_fields = _merge_fields(raw_fields, official_lookup.data)

        warnings = _final_warnings(warnings, merged_fields)

        return DocumentExtractionOutput(
            fields=merged_fields,
            raw_fields=raw_fields,
            confidence=_calculate_confidence(merged_fields, official_lookup.ok),
            warnings=warnings,
            official_lookup=official_lookup,
            debug=_build_debug(
                pdf_text_len,
                ocr_attempted_pages,
                renderer_used,
                ocr_engine_used,
                debug_enabled,
            ),
        )


def build_default_use_case() -> ExtractDocumentUseCase:
    pdf_text_extractor = PdfTextExtractor()
    pdf_renderer = PdfRenderer()
    ocr_engine = TesseractOcrEngine(language=settings.ocr_language)
    auto_extractor = AutoExtractor([GcamPdfExtractor(), MawthooqCardExtractor()])
    return ExtractDocumentUseCase(
        pdf_text_extractor=pdf_text_extractor,
        pdf_renderer=pdf_renderer,
        ocr_engine=ocr_engine,
        auto_extractor=auto_extractor,
    )


async def _lookup_gcam(license_number: str) -> OfficialLookupResult:
    response = await fetch_gcam_license(license_number)
    if not response.ok or not response.html_text:
        return OfficialLookupResult(
            performed=True,
            ok=False,
            status_code=response.status_code,
            match=False,
            data=None,
            error=response.error,
        )

    parsed = parse_gcam_html(response.html_text)
    data = OfficialData(
        license_number=parsed.get("license_number"),
        owner_name=parsed.get("owner_name"),
        license_title=parsed.get("license_title"),
        issue_date=parsed.get("issue_date"),
        expiry_date=parsed.get("expiry_date"),
        status=parsed.get("status"),
        accounts=_normalize_accounts(parsed.get("accounts") or []),
    )
    match = _normalize_key(data.license_number) == _normalize_key(license_number)
    return OfficialLookupResult(
        performed=True,
        ok=True,
        status_code=response.status_code,
        match=match,
        data=data,
        error=None,
    )


def _merge_fields(extracted: ExtractionFields, official: OfficialData) -> ExtractionFields:
    merged = ExtractionFields(**extracted.__dict__)
    if official.license_number:
        merged.license_number = official.license_number
    if official.owner_name:
        merged.owner_name = official.owner_name
    if official.license_title:
        merged.license_title = official.license_title
    if official.issue_date:
        merged.issue_date = official.issue_date
    if official.expiry_date:
        merged.expiry_date = official.expiry_date
    if official.status:
        merged.status = official.status
    if official.accounts:
        merged.accounts = official.accounts
    return merged


def _normalize_key(value: str | None) -> str:
    if not value:
        return ""
    return normalize_text(value).replace(" ", "")


def _normalize_accounts(raw_accounts: list[dict]) -> list[AccountHandle]:
    accounts: list[AccountHandle] = []
    for entry in raw_accounts:
        platform = entry.get("platform")
        handle = entry.get("handle")
        if platform and handle:
            parsed = parse_account_entry(f"{platform} - {handle}")
        else:
            parsed = None
        if not parsed:
            continue
        normalized_platform, normalized_handle = parsed
        accounts.append(AccountHandle(platform=normalized_platform, handle=normalized_handle))
    return accounts


def _calculate_confidence(fields: ExtractionFields, official_lookup_ok: bool) -> float:
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


def _final_warnings(warnings: list[str], fields: ExtractionFields) -> list[str]:
    filtered = [warning for warning in warnings if not warning.startswith("missing_")]
    if not fields.license_number:
        filtered.append("missing_license_number")
    if not fields.owner_name:
        filtered.append("missing_owner_name")
    if not fields.id_number:
        filtered.append("missing_id_number")
    if not fields.issue_date:
        filtered.append("missing_issue_date")
    if not fields.expiry_date:
        filtered.append("missing_expiry_date")
    return filtered


def _build_debug(
    pdf_text_len: int,
    ocr_attempted_pages: int,
    renderer_used: str | None,
    ocr_engine_used: str | None,
    debug_enabled: bool,
) -> DebugInfo | None:
    if not debug_enabled:
        return None
    return DebugInfo(
        pdf_text_len=pdf_text_len,
        ocr_attempted_pages=ocr_attempted_pages,
        renderer_used=renderer_used,
        ocr_engine_used=ocr_engine_used,
        tesseract_available=tesseract_available(),
        tesseract_langs_contains_ara=tesseract_has_ara(),
    )


def _should_try_gcam_owner_roi(preferred: str | None, warnings: list[str]) -> bool:
    if preferred == "gcam_pdf":
        return True
    return "matched_gcam_pdf" in warnings


def _extract_owner_name_from_gcam_roi(ocr_engine: OcrEngine, images) -> str | None:
    for image in images:
        crop = _crop_gcam_owner_region(image)
        text = ocr_engine.extract_text([crop])
        owner_name = extract_owner_name(text)
        if owner_name:
            return owner_name
    return None


def _crop_gcam_owner_region(image):
    width, height = image.size
    left = int(width * 0.05)
    right = int(width * 0.95)
    top = int(height * 0.25)
    bottom = int(height * 0.55)
    return image.crop((left, top, right, bottom))
