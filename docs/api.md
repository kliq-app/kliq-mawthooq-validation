# API Guide

## Purpose
This service fetches a public PDF/image, extracts license fields, optionally verifies via the GCAM portal, and returns merged results.

## Main flow
1) POST `/v1/extract` with `source_url` (+ optional `doc_type_hint`).
2) Service downloads and detects type.
3) OCR/text extraction runs.
4) If a license number is found, GCAM lookup runs (if enabled).
5) Response returns merged `fields`, `official_lookup` metadata, and `warnings` (raw extraction and debug details are only returned when `debug=true` or `EXTRACT_DEBUG=true`).

## Endpoints
- `GET /health` - health check.
- `POST /v1/extract` - extract license fields.
- `GET /metrics` - Prometheus metrics (only when `METRICS_ENABLED=true`).

## Authentication
- When `API_KEYS` is empty, auth is disabled.
- When `API_KEYS` is set, send `X-API-Key` on `/v1/*` requests.

## Rate limiting
- Default: 60 requests/minute per IP.
- If API keys are enabled, requests are also rate-limited per key.
- In-memory sliding window for single instance; set `REDIS_URL` for multi-instance.

## Examples
Health:
```bash
curl -s http://localhost:8000/health
```

Extract:
```bash
curl -s -X POST http://localhost:8000/v1/extract \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-key' \
  -d '{"source_url":"https://example.com/sample.pdf","doc_type_hint":"auto"}'
```

Metrics (if enabled):
```bash
curl -s http://localhost:8000/metrics
```

## Response schema (high level)
- `fields`: final merged fields (extraction + official lookup).
- `raw_extraction`: raw OCR/text extraction before official merge (debug only).
- `official_lookup`: GCAM lookup result metadata; parsed data is returned in debug mode only.
- `debug`: debug metadata (debug only).
- `warnings`: non-fatal warnings that may impact extraction quality.

## Common warnings
- `pdf_text_insufficient`: PDF text was sparse; OCR fallback attempted.
- `ocr_used`: OCR was executed.
- `ocr_failed`: OCR failed on PDF or image.
- `pdf_text_failed`: PDF text extraction failed.
- `content_type_mismatch`: Header type did not match magic bytes.
- `missing_license_number`: No license number found in extraction.
- `GCAM_LOOKUP_FAILED:<reason>`: GCAM lookup failed (timeout, 5xx, etc.).
- `GCAM_LOOKUP_CIRCUIT_OPEN`: Circuit breaker open; GCAM lookup skipped.
- `unsupported_doc_type`: Non-PDF/image content detected.
- `domain_not_allowed`: Domain blocked by `ALLOWED_DOMAINS`.
- `payload_too_large`: File exceeds `MAX_DOWNLOAD_MB`.

## Troubleshooting
- GCAM lookup skipped: check `GCAM_LOOKUP_ENABLED`, circuit breaker settings, and `ALLOWED_DOMAINS`.
- OCR disabled: ensure `OCR_ENABLED=true` and Tesseract is installed.
- SSRF blocks: ensure the URL is public and not in private IP ranges.
- Rate limit errors: increase `RATE_LIMIT_PER_MIN` or use distinct API keys.
