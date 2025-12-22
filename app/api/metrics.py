from __future__ import annotations

from fastapi import APIRouter, HTTPException, Security
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.shared.settings import settings
from app.shared.openapi import api_key_header


router = APIRouter(tags=["Metrics"], dependencies=[Security(api_key_header)])


@router.get("/metrics")
async def metrics() -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)
