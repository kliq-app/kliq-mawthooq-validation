# Configuration

Environment variables (defaults shown):

| Name | Default | Description |
| --- | --- | --- |
| `APP_ENV` | `dev` | Application environment identifier. |
| `LOG_LEVEL` | `INFO` | Log level for structured logs. |
| `MAX_DOWNLOAD_MB` | `25` | Max download size in MB. |
| `REQUEST_TIMEOUT_SEC` | `20` | Download timeout seconds. |
| `ALLOWED_DOMAINS` | empty | Optional domain allowlist (comma-separated). |
| `API_KEYS` | empty | Optional API key list (comma-separated). |
| `RATE_LIMIT_PER_MIN` | `60` | Requests per minute per IP (and per key when enabled). |
| `REDIS_URL` | empty | Optional Redis URL for rate limit counters. |
| `METRICS_ENABLED` | `false` | Expose Prometheus metrics at `/metrics`. |
| `OCR_ENABLED` | `true` | Enable OCR fallback. |
| `OCR_LANGUAGE` | `ara+eng` | Tesseract language set. |
| `MAX_OCR_PAGES` | `2` | Max PDF pages rendered for OCR. |
| `MIN_ARABIC_RATIO` | `0.05` | Minimum Arabic ratio to accept PDF text. |
| `MIN_TEXT_LENGTH` | `50` | Minimum text length to accept PDF text. |
| `GCAM_LOOKUP_ENABLED` | `true` | Enable GCAM portal lookup. |
| `GCAM_BASE_URL` | `https://elaam.gmedia.gov.sa` | GCAM base URL. |
| `GCAM_LOOKUP_TIMEOUT_SEC` | `15` | GCAM lookup timeout seconds. |
| `GCAM_LOOKUP_RETRY_COUNT` | `2` | GCAM lookup retry count. |
| `GCAM_CB_FAILURE_THRESHOLD` | `5` | GCAM circuit breaker failure threshold. |
| `GCAM_CB_RESET_SEC` | `60` | GCAM circuit breaker reset time. |
