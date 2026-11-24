# AI Personal Finance Advisor

An AI-powered personal finance application for South African users. It is designed to work from user-authorized bank exports and verified financial records. Financial calculations are performed by deterministic application logic; AI explains verified aggregate results rather than inventing financial information.

## Current implementation status

**Implemented in the repository**
- FastAPI application and IBM Cloud Code Engine deployment foundation.
- Same-origin web workspace served at /app.
- IBM Cloudant IAM connection and protected connectivity diagnostics.
- Invite-only registration, Argon2id password hashing and short-lived JWT access tokens.
- Authenticated current-user endpoint and user-scoped Cloudant document helpers.
- FNB South Africa CSV parser and authenticated preview endpoint (20 MB limit).
- Financial account, transaction, category, budget and goal API routes.
- Transaction correction history and deterministic financial summaries.
- Explicit FNB import confirmation, account matching and transaction-level duplicate detection.
- Import history metadata. The original uploaded statement is not retained in Cloudant.
- Budget progress, goal contributions, recurring-payment candidates and per-currency summaries.
- IBM watsonx.ai chat connector using IBM IAM authentication.
- Explicit per-request AI consent. Only the user's question and aggregated financial totals are sent to watsonx.ai; raw transaction descriptions, references and account IDs are excluded.
- GitHub Actions for frontend JavaScript syntax checks, strict Ruff linting and pytest.

**Implemented but gated**
- Financial account and transaction storage endpoints.
- Budget and goal storage endpoints.
- Confirmed FNB statement import and import history.
- watsonx.ai advisor chat.

Persistent finance routes require FINANCIAL_DATA_ENABLED=true. AI chat additionally requires FINANCIAL_AI_ENABLED=true and valid watsonx.ai settings. Both flags default to false. Keep them disabled until the release safeguards are complete.

**Still to implement before a complete first release**
- Production identity lifecycle: email verification, password reset, MFA, account recovery, rate limiting and session revocation.
- User-facing export, deletion and retention workflows.
- Tested Cloudant backup and restore, audit logging and operational monitoring.
- Transaction categorisation assistance, richer analytics and reports.
- watsonx.ai project/model configuration and live integration validation.
- Automated financial-data evaluation and AI quality/safety evaluation.
- Production privacy/security review and release runbook.

Do not treat gated or planned components as available for general use. Do not enable persistent financial data until the release checklist is signed off.

## Technology baseline

- Python 3.12, FastAPI and Uvicorn
- IBM Cloud Code Engine
- IBM Cloudant
- IBM watsonx.ai (chat connector implemented; project/model configuration required)
- IBM Cloud Object Storage (planned only if retained original statement files are required)

The architecture is a modular monolith. Separate services or Kubernetes will only be introduced if actual scaling or operational requirements justify them.

## Web application

Open /app on the deployed service. The workspace provides:
- Sign-in
- FNB account metadata
- FNB CSV preview and consent-based import
- Transaction history and correction
- Categories
- Budgets and spending progress
- Financial goals and contribution tracking
- Financial summaries and recurring-payment candidates
- AI advisor chat, once the finance and AI feature gates are enabled

The bearer access token is kept in page memory only. It is cleared when the page is reloaded or signed out. It is not stored in localStorage or sessionStorage.

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install development dependencies with: python -m pip install -r requirements-dev.txt
3. Copy .env.example to .env and configure only the values needed for the work. Never commit .env.
4. Keep FINANCIAL_DATA_ENABLED=false and FINANCIAL_AI_ENABLED=false until all release safeguards have passed.
5. Start the API with: uvicorn main:app --reload --host 127.0.0.1 --port 8080
6. Open http://127.0.0.1:8080/app for the web workspace and http://127.0.0.1:8080/docs for the API documentation.

## Authentication API

- POST /auth/register: invite-only registration. Requires X-Registration-Invite.
- POST /auth/token: exchange email and password for a short-lived bearer token.
- GET /auth/me: return the authenticated account. Requires Authorization: Bearer token.

Required server-side settings: JWT_SECRET_KEY, AUTH_EMAIL_INDEX_KEY, and (to enable registration) REGISTRATION_INVITE_CODE. Keep cryptographic keys independent and at least 32 bytes long. Do not put their values in source control.

## Finance API

All routes below require authentication. Persistent finance routes also require FINANCIAL_DATA_ENABLED=true.

- /api/v1/accounts: create and manage linked-account metadata. The application does not request FNB online banking credentials.
- /api/v1/transactions: create, retrieve, update, filter and soft-delete transactions.
- /api/v1/categories: read built-in categories and manage user categories.
- /api/v1/budgets: create, list, update and deactivate budgets.
- /api/v1/budgets/progress: calculate budget use from saved transactions.
- /api/v1/goals: create, list, update and deactivate financial goals.
- /api/v1/goals/{id}/contributions: record goal contributions and withdrawals.
- /api/v1/analytics/summary: deterministic income, expense, transfer and net cash-flow totals, grouped by currency.
- /api/v1/analytics/recurring-payments: identify possible recurring debits from the user's transaction history.
- POST /imports/fnb/csv/preview: parse an FNB CSV and return a limited preview without saving transactions.
- POST /imports/fnb/csv/confirm: explicitly confirm and persist a validated FNB CSV against a selected, user-owned FNB account.
- /imports: view import metadata and status.

FNB imports require the account's last four digits to match the statement. The import process stores a file hash and import metadata, not the original statement. Stable transaction identifiers prevent the same transaction from being stored again when statements overlap.

## AI advisor

POST /api/v1/advisor/chat requires both feature gates and an explicit consent_to_share_summary=true field. It sends the question and a user-specific aggregate summary to IBM watsonx.ai. It does not send raw transaction rows, descriptions, references or account IDs. Questions and responses are not persisted by the current chat route.

The following IBM settings are required:
- WATSONX_APIKEY (store as a Code Engine secret)
- WATSONX_PROJECT_ID
- WATSONX_URL
- WATSONX_MODEL_ID
- WATSONX_API_VERSION

For the Frankfurt region, the current default service URL is https://eu-de.ml.cloud.ibm.com. Use the endpoint and API version shown in the Developer access page for the actual watsonx project.

## Tests and code quality

Run tests with pytest and lint with ruff check . GitHub Actions validates the frontend JavaScript syntax, runs strict Ruff checks and executes pytest. Automated fixtures must not contain invented financial histories or example transaction amounts.

## Container build

Build with: docker build -t financial-advisor:local .
Run with: docker run --rm -p 8080:8080 --env-file .env financial-advisor:local

The container runs as a non-root user. The Dockerfile copies the same-origin frontend with the application.

## Data protection

- Never put API keys, passwords, tokens, bank statements or real financial data in GitHub, commits, tests or logs.
- Persistent financial data and AI features are disabled by default.
- Keep both disabled until user consent, ownership isolation, backup/restore, retention, deletion, audit logging and applicable privacy review are complete.
- Preserve original imported transaction fields when users make corrections.
- Financial amounts must be calculated using exact decimal arithmetic. AI must not invent balances, transactions or financial metrics.
