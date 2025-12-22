# Architecture

## Structure
- `app/api`: HTTP routes and schemas.
- `app/application`: use cases (orchestration).
- `app/domain`: domain models and result types.
- `app/infrastructure`: external clients, OCR, PDF handling, extractors.
- `app/shared`: cross-cutting concerns (settings, logging, middleware, metrics).

## Extraction pipeline
1) Fetch content with SSRF protections and size limits.
2) Detect file type by header and magic bytes.
3) PDF: extract text; if insufficient Arabic, render pages and OCR.
4) Image: OCR directly.
5) Parse text for fields.
6) Optional GCAM lookup and merge official fields.

## GCAM lookup flow
- Only runs when a license number is present and `GCAM_LOOKUP_ENABLED=true`.
- Circuit breaker trips after repeated failures and skips lookup for a cooldown window.
- All failures are non-fatal and reported in warnings.

## SSRF protections
- Only `http/https` URLs allowed.
- Localhost/private ranges are blocked.
- Optional domain allowlist via `ALLOWED_DOMAINS`.

## Parsers and extractors
- Parsers live in `app/infrastructure/parsing/fields.py`.
- Extractor strategies live in `app/infrastructure/extractors/strategies.py`.
- Add new strategy by implementing `matches()` and `extract()` and registering it in `build_default_use_case`.
