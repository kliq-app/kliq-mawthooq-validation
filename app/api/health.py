from __future__ import annotations

from fastapi import APIRouter, Security

from app.shared.openapi import api_key_header

router = APIRouter(tags=["Health"], dependencies=[Security(api_key_header)])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "license-extractor-service"}
