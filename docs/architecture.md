# Architecture

## Current approach

The project starts as a modular monolith: one FastAPI application deployed as one IBM Cloud Code Engine application. This keeps the prototype inexpensive and operationally simple while keeping code boundaries clear.

## Intended boundaries

- `api/routes`: HTTP routing and transport concerns.
- `schemas`: request and response validation.
- `services`: use cases and business rules.
- `database`: persistence and repository interfaces/implementations.
- `models`: domain and persisted data structures.
- `integrations`: external provider clients.
- `core`: configuration, logging and cross-cutting concerns.

## Planned data flow

Client -> FastAPI route -> validated schema -> service/use case -> repository or provider integration -> response schema.

AI-generated explanations must use application-calculated, verified figures. Deterministic code remains authoritative for balances, totals, budgets and cash-flow calculations.

## Planned IBM services

- Code Engine: API container hosting.
- Cloudant: document persistence. Existing database: `finance-advisor-db`.
- watsonx.ai: planned AI inference and language tasks.
- Cloud Object Storage: planned uploaded statement/document storage, subject to retention and privacy design.

These integrations are not implemented merely because configuration placeholders exist.

## API compatibility

The root-level `main.py` re-exports `app.main:app` so the existing container command `uvicorn main:app` remains valid.
