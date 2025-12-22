# ADR 0001: Clean Architecture Layout

## Status
Accepted

## Context
We need a maintainable FastAPI service that separates HTTP concerns from extraction logic and external integrations.

## Decision
Adopt a clean architecture layout:
- `api` for HTTP routes and schemas
- `application` for use cases
- `domain` for core models
- `infrastructure` for IO, OCR, PDF handling, and portal clients
- `shared` for cross-cutting utilities

## Consequences
- Improved testability and modularity.
- Slightly more structure/boilerplate, but clearer boundaries.
