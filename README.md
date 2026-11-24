# AI Personal Finance Advisor

An AI-powered personal finance application for South African users. It is designed to work from user-authorized bank exports and verified financial records. Financial calculations are performed by deterministic application logic; AI will explain or classify verified results rather than invent financial information.

## Current implementation status

**Implemented in the repository**
- FastAPI application and IBM Cloud Code Engine deployment foundation.
- IBM Cloudant IAM connection and protected connectivity diagnostics.
- Invite-only registration, Argon2id password hashing and short-lived JWT access tokens.
- Authenticated current-user endpoint and user-scoped Cloudant document helpers.
- FNB South Africa CSV parser and authenticated preview endpoint (20 MB limit).
- Financial account, transaction, category, budget and goal API routes.
- Transaction correction history and deterministic financial summaries.
- Explicit FNB import confirmation, account matching and transaction-level duplicate detection.
- Import history metadata. The original uploaded statement is not retained in Cloudant.
- GitHub Actions for strict Ruff linting and pytest.

**Implemented but gated**
- Financial account and transaction storage endpoints.
- Budget and goal storage endpoints.
- Confirmed FNB statement import and import history.

These routes require FINANCIAL_DATA_ENABLED=true. The setting defaults to false. Keep it disabled until backup/restore, retention, deletion, audit and privacy release controls have been completed and verified.

**Still to implement before a complete first release**
- Production identity lifecycle: email verification, password reset, MFA, account recovery and session revocation.
- Tested Cloudant backup and restore, retention/deletion workflows and operational audit logging.
- Budget usage tracking, savings-goal contributions and recurring-payment detection.
- Full transaction categorisation assistance and financial reports.
- IBM watsonx.ai integration with verified-data grounding and AI usage controls.
- User-facing web application.
- Production privacy/security review and release runbook.

Do not treat planned components as working functionality. Do not enable persistent financial data until the release checklist is signed off.

## Technology baseline

- Python 3.12, FastAPI and Uvicorn
- IBM Cloud Code Engine
- IBM Cloudant
- IBM watsonx.ai (planned)
- IBM Cloud Object Storage (planned for retained original statements, if required)

The architecture is a modular monolith. Separate services or Kubernetes will only be introduced if actual scaling or operational requirements justify them.

## Repository structure

- app/api/routes: HTTP endpoints
- app/core: application configuration and shared concerns
- app/database: Cloudant access and owner-scoped persistence
- app/integrations: external provider clients
- app/schemas: API request and response validation
- app/services: application and business logic
- tests: automated tests
- docs: architecture, security and delivery documentation
- .github/workflows: continuous integration

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install development dependencies with: python -m pip install -r requirements-dev.txt
3. Copy .env.example to .env and configure only the values needed for the work. Never commit .env.
4. Keep FINANCIAL_DATA_ENABLED=false until all release safeguards have passed.
5. Start the API with: uvicorn main:app --reload --host 127.0.0.1 --port 8080
6. Open the API at http://127.0.0.1:8080/ and interactive docs at http://127.0.0.1:8080/docs.

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
- /api/v1/goals: create, list, update and deactivate financial goals.
- /api/v1/analytics/summary: deterministic income, expense, net cash-flow and category totals, grouped by currency.
- POST /imports/fnb/csv/preview: parse an FNB CSV and return a limited preview without saving transactions.
- POST /imports/fnb/csv/confirm: explicitly confirm and persist a validated FNB CSV against a selected, user-owned FNB account.
- /imports: view import metadata and status.

FNB imports require the account's last four digits to match the statement. The import process stores a file hash and import metadata, not the original statement. Stable transaction identifiers prevent the same transaction from being stored again when statements overlap.

## Tests and code quality

Run tests with pytest and lint with ruff check . GitHub Actions runs strict lint checks and tests on pushes and pull requests to main. Automated fixtures must not contain invented financial histories or example transaction amounts.

## Container build

Build with: docker build -t financial-advisor:local .
Run with: docker run --rm -p 8080:8080 --env-file .env financial-advisor:local

The container runs as a non-root user. Docker build exclusions are maintained in .dockerignore.

## Data protection

- Never put API keys, passwords, tokens, bank statements or real financial data in GitHub, commits, tests or logs.
- Persistent financial data is disabled by default.
- Keep it disabled until user consent, ownership isolation, backup/restore, retention, deletion, audit logging and applicable privacy review are complete.
- Preserve original imported transaction fields when users make corrections.
- Financial amounts must be calculated using exact decimal arithmetic. AI must not invent balances, transactions or financial metrics.
