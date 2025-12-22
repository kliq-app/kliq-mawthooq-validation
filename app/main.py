from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.v1.routes import router as v1_router
from app.shared.handlers import (
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.shared.logging import setup_logging
from app.shared.metrics_middleware import MetricsMiddleware
from app.shared.middleware import RequestContextMiddleware
from app.shared.security_middleware import SecurityMiddleware
from app.shared.settings import settings
from app.shared.errors import AppError
from app.shared.dependencies import log_dependency_status


def create_app() -> FastAPI:
    setup_logging(settings.log_level)
    log_dependency_status()

    description = (
        "Service that ingests PDFs/images, extracts license data, "
        "optionally verifies via GCAM, and returns merged results."
    )
    tags_metadata = [
        {"name": "Health", "description": "Service health checks."},
        {"name": "Extraction", "description": "License extraction and GCAM merge."},
        {"name": "Metrics", "description": "Prometheus metrics (if enabled)."},
    ]

    application = FastAPI(
        title="License Extractor Service",
        description=description,
        version="1.0.0",
        contact={"name": "Support", "email": "support@example.com"},
        license_info={"name": "Proprietary", "url": "https://example.com/license"},
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=tags_metadata,
    )
    application.add_middleware(SecurityMiddleware)
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(MetricsMiddleware)
    application.include_router(health_router)
    application.include_router(v1_router)
    if settings.metrics_enabled:
        application.include_router(metrics_router)

    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(AppError, app_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)

    return application


app = create_app()
