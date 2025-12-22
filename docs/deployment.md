# Deployment

## Docker
```bash
docker build -t license-extractor-service .
docker run --rm -p 8000:8000 --env-file .env license-extractor-service
```

## Docker Compose
```bash
docker compose up --build
```

## Production command
Recommended starting point (CPU-bound OCR):
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```
Adjust workers based on CPU and OCR load. OCR is CPU-heavy.

## Health checks
- Use `GET /health` for liveness and readiness checks.

## Observability
- Enable Prometheus metrics with `METRICS_ENABLED=true`.
- Scrape `GET /metrics` at a short interval (e.g., 15s).

## Kubernetes (brief)
- Define a Deployment with a readinessProbe on `/health`.
- Use resource limits to avoid OCR saturation.
- Add a ServiceMonitor or scrape config for `/metrics` when enabled.
