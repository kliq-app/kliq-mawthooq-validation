from __future__ import annotations

from dataclasses import asdict
import logging

from fastapi import APIRouter, Query, Security
from fastapi.responses import JSONResponse

from app.api.v1.schemas import (
    ExtractRequest,
    ExtractResponse,
    ExtractedFields,
    DebugInfo,
    OfficialLookup,
    OfficialLookupData,
    OfficialLookupError,
    SourceInfo,
)
from app.application.use_cases.extract_document import build_default_use_case
from app.infrastructure.fetcher import fetch_content
from app.shared.openapi import api_key_header
from app.shared.redaction import redact_payload
from app.shared.errors import ErrorResponse
from app.shared.settings import settings


logger = logging.getLogger("app.extract")
router = APIRouter(prefix="/v1", tags=["Extraction"], dependencies=[Security(api_key_header)])
use_case = build_default_use_case()


@router.post(
    "/extract",
    response_model=ExtractResponse,
    summary="Extract license fields from a PDF or image",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
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
                    }
                }
            }
        },
        401: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {"code": "unauthorized", "message": "API key required"}
                    }
                }
            },
        },
        429: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {"code": "rate_limited", "message": "Rate limit exceeded"}
                    }
                }
            },
        },
        422: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "validation_error",
                            "message": "Invalid request",
                            "details": [],
                        }
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "internal_error",
                            "message": "Unexpected error",
                        }
                    }
                }
            },
        },
    },
)
async def extract_document(
    payload: ExtractRequest,
    debug: bool = Query(False, description="Include raw extraction and debug fields."),
) -> ExtractResponse:
    logger.info("extract.request", extra={"payload": redact_payload(payload.model_dump())})
    debug_enabled = debug or settings.extract_debug
    result = await fetch_content(payload.source_url)
    extraction = await use_case.execute(
        result.content,
        result.detected_type,
        payload.doc_type_hint,
        debug=debug_enabled,
    )
    warnings = result.warnings + extraction.warnings
    official = extraction.official_lookup
    official_data = (
        OfficialLookupData(**asdict(official.data)) if debug_enabled and official.data else None
    )
    official_error = (
        OfficialLookupError(message=official.error) if debug_enabled and official.error else None
    )
    response_payload = ExtractResponse(
        doc_type=result.detected_type,
        source=SourceInfo(
            url=result.url,
            content_type=result.content_type,
            size_bytes=result.size_bytes,
        ),
        fields=ExtractedFields(**asdict(extraction.fields)),
        raw_extraction=ExtractedFields(**asdict(extraction.raw_fields)) if debug_enabled else None,
        confidence=extraction.confidence,
        warnings=warnings,
        official_lookup=OfficialLookup(
            performed=official.performed,
            ok=official.ok,
            status_code=official.status_code,
            match=official.match,
            data=official_data,
            error=official_error,
        ),
    )
    if debug_enabled and extraction.debug:
        response_payload.debug = DebugInfo(**asdict(extraction.debug))

    response_payload_data = response_payload.model_dump()
    if not debug_enabled:
        response_payload_data.pop("raw_extraction", None)
        response_payload_data.pop("debug", None)
        official_payload = response_payload_data.get("official_lookup", {})
        official_payload.pop("data", None)
        official_payload.pop("error", None)
        response_payload_data["official_lookup"] = official_payload

    logger.info("extract.response", extra={"response": redact_payload(response_payload_data)})
    return JSONResponse(content=response_payload_data)
