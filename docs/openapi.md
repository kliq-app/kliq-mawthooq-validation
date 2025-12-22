# OpenAPI and Swagger

## UI
- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`

## Export OpenAPI JSON
```bash
curl -s http://localhost:8000/openapi.json
```

## Versioning
- Public APIs are under the `/v1` prefix.
- Backward-incompatible changes should introduce a new `/v2` prefix.
