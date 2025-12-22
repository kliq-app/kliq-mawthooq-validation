from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExtractionFields:
    license_number: Optional[str] = None
    owner_name: Optional[str] = None
    id_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None
    license_title: Optional[str] = None
    status: Optional[str] = None
    accounts: List["AccountHandle"] = field(default_factory=list)


@dataclass
class ExtractionResult:
    fields: ExtractionFields
    confidence: float
    warnings: List[str] = field(default_factory=list)


@dataclass
class OfficialData:
    license_number: Optional[str] = None
    owner_name: Optional[str] = None
    license_title: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[str] = None
    accounts: List["AccountHandle"] = field(default_factory=list)


@dataclass
class OfficialLookupResult:
    performed: bool
    ok: bool
    status_code: Optional[int]
    match: bool
    data: Optional[OfficialData]
    error: Optional[str]


@dataclass
class AccountHandle:
    platform: Optional[str]
    handle: str


@dataclass
class DebugInfo:
    pdf_text_len: int
    ocr_attempted_pages: int
    renderer_used: Optional[str]
    ocr_engine_used: Optional[str]
    tesseract_available: bool
    tesseract_langs_contains_ara: bool


@dataclass
class DocumentExtractionOutput:
    fields: ExtractionFields
    raw_fields: ExtractionFields
    confidence: float
    warnings: List[str]
    official_lookup: OfficialLookupResult
    debug: Optional[DebugInfo] = None
