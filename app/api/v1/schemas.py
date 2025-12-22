from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class PlatformEnum(str, Enum):
    snapchat = "snapchat"
    tiktok = "tiktok"
    youtube = "youtube"
    instagram = "instagram"
    twitter = "twitter"


DocTypeHint = Literal["auto", "gcam_pdf", "mawthooq_card", "gcam_page"]
DetectedDocType = Literal["pdf", "image", "html", "unknown"]


class AccountHandle(BaseModel):
    platform: PlatformEnum = Field(..., description="Normalized platform enum.")
    handle: str = Field(..., description="Account handle or username.")


class ExtractRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "source_url": "https://example.com/sample.pdf",
                    "doc_type_hint": "auto",
                }
            ]
        }
    )

    source_url: str = Field(
        ...,
        description="Public URL to the document (PDF or image).",
        examples=["https://example.com/sample.pdf"],
    )
    doc_type_hint: DocTypeHint = Field(
        "auto",
        description="Optional hint about document type.",
        examples=["auto"],
    )


class SourceInfo(BaseModel):
    url: str = Field(..., description="Fetched URL after redirects.")
    content_type: Optional[str] = Field(None, description="Content-Type header if provided.")
    size_bytes: int = Field(..., description="Downloaded payload size in bytes.")


class ExtractedFields(BaseModel):
    license_number: Optional[str] = Field(None, description="License number.")
    owner_name: Optional[str] = Field(None, description="Owner or license holder name.")
    id_number: Optional[str] = Field(None, description="National ID or identity number.")
    issue_date: Optional[str] = Field(None, description="Issue date in ISO format (YYYY-MM-DD).")
    expiry_date: Optional[str] = Field(None, description="Expiry date in ISO format (YYYY-MM-DD).")
    city: Optional[str] = Field(None, description="City name.")
    district: Optional[str] = Field(None, description="District or neighborhood name.")
    street: Optional[str] = Field(None, description="Street name.")
    license_title: Optional[str] = Field(None, description="License title/type.")
    status: Optional[str] = Field(None, description="License status.")
    accounts: List["AccountHandle"] = Field(default_factory=list, description="Associated accounts or handles.")


class OfficialLookupData(BaseModel):
    license_number: Optional[str] = Field(None, description="Official license number.")
    owner_name: Optional[str] = Field(None, description="Official owner/license holder.")
    license_title: Optional[str] = Field(None, description="Official license title/type.")
    issue_date: Optional[str] = Field(None, description="Official issue date in ISO format.")
    expiry_date: Optional[str] = Field(None, description="Official expiry date in ISO format.")
    status: Optional[str] = Field(None, description="Official license status.")
    accounts: List["AccountHandle"] = Field(default_factory=list, description="Official accounts/handles if present.")


class OfficialLookupError(BaseModel):
    message: str = Field(..., description="Lookup error message.")


class OfficialLookup(BaseModel):
    performed: bool = Field(..., description="Whether lookup was attempted.")
    ok: bool = Field(..., description="Whether lookup succeeded.")
    status_code: Optional[int] = Field(None, description="HTTP status code from GCAM.")
    match: bool = Field(..., description="Whether official license number matched extracted.")
    data: Optional[OfficialLookupData] = Field(
        None,
        description="Parsed official data (debug only).",
    )
    error: Optional[OfficialLookupError] = Field(
        None,
        description="Lookup error details if any (debug only).",
    )


class DebugInfo(BaseModel):
    pdf_text_len: int = Field(..., description="Length of extracted PDF text after normalization.")
    ocr_attempted_pages: int = Field(..., description="Number of pages attempted for OCR.")
    renderer_used: Optional[str] = Field(None, description="PDF renderer used for OCR fallback.")
    ocr_engine_used: Optional[str] = Field(None, description="OCR engine identifier.")
    tesseract_available: bool = Field(..., description="Whether tesseract is installed.")
    tesseract_langs_contains_ara: bool = Field(..., description="Whether Arabic language data is available.")


class ExtractResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "doc_type": "pdf",
                    "source": {
                        "url": "https://example.com/license.pdf",
                        "content_type": "application/pdf",
                        "size_bytes": 120340,
                    },
                    "fields": {
                        "license_number": "123456",
                        "owner_name": "موسى ابراهيم موسى آل جوير",
                        "id_number": None,
                        "issue_date": "2024-01-20",
                        "expiry_date": "2025-01-20",
                        "city": "الرياض",
                        "district": None,
                        "street": None,
                        "license_title": "ترخيص إعلامي",
                        "status": "ساري",
                        "accounts": [{"platform": "twitter", "handle": "@example"}],
                    },
                    "confidence": 0.78,
                    "warnings": [],
                    "official_lookup": {
                        "performed": True,
                        "ok": True,
                        "status_code": 200,
                        "match": True,
                    },
                },
                {
                    "doc_type": "pdf",
                    "source": {
                        "url": "https://example.com/mawthooq.pdf",
                        "content_type": "application/pdf",
                        "size_bytes": 45230,
                    },
                    "fields": {
                        "license_number": None,
                        "owner_name": "زايد ساير زايد الشهري",
                        "id_number": None,
                        "issue_date": None,
                        "expiry_date": None,
                        "city": None,
                        "district": None,
                        "street": None,
                        "license_title": "بطاقة موثوق",
                        "status": None,
                        "accounts": [],
                    },
                    "confidence": 0.47,
                    "warnings": ["missing_license_number"],
                    "official_lookup": {
                        "performed": False,
                        "ok": False,
                        "status_code": None,
                        "match": False,
                    },
                }
            ]
        }
    )

    doc_type: DetectedDocType = Field(..., description="Detected document type.")
    source: SourceInfo = Field(..., description="Source metadata for the fetched document.")
    fields: ExtractedFields = Field(..., description="Final merged extraction fields.")
    raw_extraction: Optional[ExtractedFields] = Field(
        None,
        description="Raw OCR/text extraction before official merge (debug only).",
    )
    confidence: float = Field(..., description="Overall confidence score from 0 to 1.")
    warnings: List[str] = Field(default_factory=list, description="Warnings encountered during extraction.")
    official_lookup: OfficialLookup = Field(..., description="Official GCAM lookup result.")
    debug: Optional[DebugInfo] = Field(None, description="Debug metadata (no PII, debug only).")
