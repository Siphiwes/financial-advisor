# Architecture

## Current approach

The project is a modular monolith: one FastAPI application deployed as one IBM Cloud Code Engine application. The web workspace is served from the same application under /app, with assets under /assets. This keeps browser/API requests same-origin and avoids a separate frontend deployment.

## Component boundaries

- api/routes: HTTP routing and authentication dependencies.
- schemas: request and response validation.
- services: finance business logic, import orchestration and deterministic calculations.
- database: Cloudant access and owner-scoped persistence.
- integrations: external provider clients, including IBM watsonx.ai.
- core: configuration and cross-cutting concerns.
- static: same-origin HTML, CSS and JavaScript web workspace.

## Financial data flow

Browser -> authenticated FastAPI route -> validated schema -> finance service -> owner-scoped Cloudant records -> deterministic calculations -> response.

The authenticated user ID is derived from the validated access token and Cloudant user document. It is never accepted from a finance request body.

## FNB import flow

FNB CSV upload -> in-memory parser -> user review -> explicit consent -> selected user-owned FNB account match -> retry-safe import batch and user-scoped transaction records.

Only import metadata and a file hash are retained. The original uploaded CSV is not retained by this implementation.

## AI advisor flow

Authenticated user question + explicit one-request consent -> deterministic user-specific financial summary -> IBM watsonx.ai chat API -> response.

The financial chat sends aggregate figures (income, expenses, transfers, cash flow and expense categories), the selected date range and the user's question. The category-suggestion flow sends one explicitly selected transaction's date, description, amount and currency plus the allowed category names/types. Neither flow sends account IDs, references or source files. Prompts and responses are not persisted by the current endpoints.

The AI integration is separately disabled by default. Financial calculations remain authoritative; AI explanations cannot modify financial records.

## IBM services

- Code Engine: API and same-origin frontend hosting.
- Cloudant: user identity and financial document persistence. Existing database: finance-advisor-db.
- watsonx.ai Runtime: AI chat inference, configured by region, project ID, model ID and API version.
- Cloud Object Storage: not currently used. Consider only if a product requirement calls for retaining original statement files with a defined retention/deletion design.

## Deployment compatibility

The root main.py re-exports app.main:app so the existing container command uvicorn main:app remains valid. The Dockerfile copies the whole app/ directory, including static assets.
