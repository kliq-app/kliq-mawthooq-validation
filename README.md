# License Extractor Service

Stateless FastAPI service for license ingestion, content detection, extraction, and optional GCAM lookup.

## Requirements
- Python 3.11+
- Tesseract OCR with Arabic language pack for OCR paths

## Docs
- `docs/api.md`
- `docs/openapi.md`
- `docs/architecture.md`
- `docs/configuration.md`
- `docs/deployment.md`
- `docs/CHANGELOG.md`

## Quickstart
### Local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Install Tesseract (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng
```

```bash
uvicorn app.main:app --reload
```

### Docker
```bash
docker compose up --build
```

## Endpoints
### Health
```bash
curl -s http://localhost:8000/health
```

### Extract
```bash
curl -s -X POST http://localhost:8000/v1/extract \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: your-key' \
  -d '{"source_url":"https://example.com/sample.pdf","doc_type_hint":"auto"}'
```

Example response shape:
```json
{
  "doc_type": "pdf",
  "source": {"url":"...","content_type":"application/pdf","size_bytes":12345},
  "fields": {
    "license_number":"123456",
    "owner_name":"موسى ابراهيم موسى آل جوير",
    "accounts":[{"platform":"twitter","handle":"example"}]
  },
  "confidence": 0.78,
  "warnings": [],
  "official_lookup": {
    "performed": true,
    "ok": true,
    "status_code": 200,
    "match": true
  }
}
```

Mawthooq example (owner name present):
```json
{
  "doc_type": "pdf",
  "source": {"url":"...","content_type":"application/pdf","size_bytes":45230},
  "fields": {
    "license_number":null,
    "owner_name":"زايد ساير زايد الشهري",
    "license_title":"بطاقة موثوق",
    "accounts":[]
  },
  "confidence": 0.47,
  "warnings": ["missing_license_number"],
  "official_lookup": {"performed": false, "ok": false, "status_code": null, "match": false}
}
```

### Metrics
```bash
curl -s http://localhost:8000/metrics
```

## Extraction logic
- PDFs: try text extraction first; if Arabic text is insufficient, render first pages and OCR.
- Images: OCR directly.
- Auto extractor uses GCAM/Mawthooq heuristics and falls back to generic field parsing.
- `doc_type_hint` supports: `auto`, `gcam_pdf`, `mawthooq_card`, `gcam_page`.

## Environment variables
- `API_KEYS` (comma-separated, empty disables auth)
- `RATE_LIMIT_PER_MIN` (default `60`, per IP and per key when enabled)
- `REDIS_URL` (optional, enables Redis-backed rate limiting)
- `METRICS_ENABLED` (default `false`)
- `OCR_ENABLED` (default `true`)
- `OCR_LANGUAGE` (default `ara+eng`)
- `MAX_OCR_PAGES` (default `2`)
- `MIN_ARABIC_RATIO` (default `0.05`)
- `MIN_TEXT_LENGTH` (default `50`)
- `GCAM_LOOKUP_ENABLED` (default `true`)
- `GCAM_BASE_URL` (default `https://elaam.gmedia.gov.sa`)
- `GCAM_LOOKUP_TIMEOUT_SEC` (default `15`)
- `GCAM_LOOKUP_RETRY_COUNT` (default `2`)
- `GCAM_CB_FAILURE_THRESHOLD` (default `5`)
- `GCAM_CB_RESET_SEC` (default `60`)

If `ALLOWED_DOMAINS` is set, include `elaam.gmedia.gov.sa` to allow official lookup.

## Security and limits
- When `API_KEYS` is set, `/v1/*` requests must include `X-API-Key`.
- Rate limiting uses an in-memory sliding window by default (single-instance). If `REDIS_URL` is set, Redis is used for multi-instance limits.
- Metrics are available at `GET /metrics` when `METRICS_ENABLED=true`.
- SSRF protections block localhost and private ranges during URL fetch.
- Logs are PII-safe: ID numbers and owner names are redacted.

## How to add a new document type extractor
- Add a new extractor class in `app/infrastructure/extractors/strategies.py`.
- Add parsing patterns in `app/infrastructure/parsing/fields.py`.
- Register the extractor in `build_default_use_case` in `app/application/use_cases/extract_document.py`.

## Tooling
```bash
make format
make lint
make test
```
