from __future__ import annotations

import time
from typing import Callable

from prometheus_client import Counter, Histogram

from app.shared.settings import settings


REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
DOWNLOAD_SIZE = Histogram(
    "download_size_bytes",
    "Downloaded content size in bytes",
    buckets=(1024, 10 * 1024, 100 * 1024, 1024 * 1024, 5 * 1024 * 1024, 25 * 1024 * 1024),
)
DOC_TYPE_COUNT = Counter(
    "sniffed_doc_type_total",
    "Sniffed document type counts",
    ["doc_type"],
)
OCR_USED = Counter(
    "ocr_used_total",
    "OCR usage count",
    ["doc_type"],
)
OCR_DURATION = Histogram(
    "ocr_duration_seconds",
    "OCR duration in seconds",
    ["doc_type"],
)
GCAM_LOOKUP_TOTAL = Counter(
    "gcam_lookup_total",
    "GCAM lookup results",
    ["result"],
)
GCAM_LOOKUP_DURATION = Histogram(
    "gcam_lookup_duration_seconds",
    "GCAM lookup duration in seconds",
    ["result"],
)


class Metrics:
    def __init__(self, enabled_fn: Callable[[], bool]) -> None:
        self._enabled_fn = enabled_fn

    def _enabled(self) -> bool:
        return self._enabled_fn()

    def observe_request(self, method: str, path: str, status_code: int, duration: float) -> None:
        if not self._enabled():
            return
        REQUEST_COUNT.labels(method=method, path=path, status_code=str(status_code)).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

    def observe_download(self, size_bytes: int, doc_type: str) -> None:
        if not self._enabled():
            return
        DOWNLOAD_SIZE.observe(size_bytes)
        DOC_TYPE_COUNT.labels(doc_type=doc_type).inc()

    def observe_ocr(self, doc_type: str, duration: float) -> None:
        if not self._enabled():
            return
        OCR_USED.labels(doc_type=doc_type).inc()
        OCR_DURATION.labels(doc_type=doc_type).observe(duration)

    def observe_gcam_lookup(self, result: str, duration: float) -> None:
        if not self._enabled():
            return
        GCAM_LOOKUP_TOTAL.labels(result=result).inc()
        GCAM_LOOKUP_DURATION.labels(result=result).observe(duration)

    @staticmethod
    def now() -> float:
        return time.monotonic()


metrics = Metrics(lambda: settings.metrics_enabled)
