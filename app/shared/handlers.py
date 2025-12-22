from __future__ import annotations

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.errors import AppError, ErrorDetail, ErrorResponse


logger = logging.getLogger("app.errors")


def _json_error(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning("http_exception", extra={"status_code": exc.status_code})
    return _json_error(exc.status_code, "http_error", str(exc.detail))


def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _json_error(422, "validation_error", "Invalid request", exc.errors())


def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    return _json_error(exc.status_code, exc.code, exc.message, exc.details)


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception")
    return _json_error(500, "internal_error", "Unexpected error")
