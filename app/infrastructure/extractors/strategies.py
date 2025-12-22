from __future__ import annotations

from typing import Iterable, Optional

from app.domain.models import ExtractionFields, ExtractionResult
from app.infrastructure.parsing.fields import extract_fields_from_text, extract_owner_name


class BaseExtractor:
    name = "base"

    def matches(self, text: str) -> bool:
        return False

    def extract(self, text: str) -> ExtractionResult:
        fields = extract_fields_from_text(text)
        confidence = _confidence_from_fields(fields)
        return ExtractionResult(fields=fields, confidence=confidence, warnings=[])


class GcamPdfExtractor(BaseExtractor):
    name = "gcam_pdf"

    def matches(self, text: str) -> bool:
        return _has_any(text, ["ترخيص إعلامي", "الهيئة العامة لتنظيم الإعلام", "gcam"])  # GCAM hints

    def extract(self, text: str) -> ExtractionResult:
        fields = extract_fields_from_text(text)
        owner_name = extract_owner_name(text)
        if owner_name:
            fields.owner_name = owner_name
        confidence = _confidence_from_fields(fields)
        return ExtractionResult(fields=fields, confidence=confidence, warnings=[])


class MawthooqCardExtractor(BaseExtractor):
    name = "mawthooq_card"

    def matches(self, text: str) -> bool:
        return _has_any(text, ["بطاقة موثوق", "موثوق", "mawthooq", "موثوقية"])  # Mawthooq hints

    def extract(self, text: str) -> ExtractionResult:
        fields = extract_fields_from_text(text)
        owner_name = extract_owner_name(text)
        if owner_name:
            fields.owner_name = owner_name
        confidence = _confidence_from_fields(fields)
        return ExtractionResult(fields=fields, confidence=confidence, warnings=[])


class AutoExtractor:
    def __init__(self, extractors: Iterable[BaseExtractor]) -> None:
        self.extractors = list(extractors)

    def extract(self, text: str, preferred: Optional[str] = None) -> ExtractionResult:
        if preferred:
            for extractor in self.extractors:
                if extractor.name == preferred:
                    result = extractor.extract(text)
                    result.warnings.append("forced_extractor")
                    return result

        for extractor in self.extractors:
            if extractor.matches(text):
                result = extractor.extract(text)
                result.warnings.append(f"matched_{extractor.name}")
                return result

        return BaseExtractor().extract(text)


def _has_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _confidence_from_fields(fields: ExtractionFields) -> float:
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
    return max(0.20, min(0.95, round(score, 2)))
