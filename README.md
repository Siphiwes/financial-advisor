# AI Personal Finance Advisor

An AI-powered personal finance application for South African users. It is designed to work from user-authorized bank exports and verified financial records. Financial calculations are performed by deterministic application logic; AI explains verified aggregate results rather than inventing financial information.

## Current implementation status

**Implemented in the repository**
- FastAPI application and IBM Cloud Code Engine deployment foundation.
- Same-origin web workspace served at /app.
- IBM Cloudant IAM connection and protected connectivity diagnostics.
- Invite-only registration, Argon2id password hashing and short-lived JWT access tokens.
- One-time email verification and password recovery using expiring, single-use Cloudant-backed token digests.
- Authenticated TLS SMTP email delivery, configured for personal Gmail through an IBM Code Engine secret.
- Password change and all-session revocation after current-password verification.
- Authenticated current-user endpoint and user-scoped Cloudant document helpers.
- FNB South Africa CSV parser with metadata-row detection and authenticated preview endpoint (20 MB limit).
- FNB South Africa PDF transaction-table parser, authenticated preview and explicit confirmed-import endpoints (20 MB limit).
- Financial account, transaction, category, budget and goal API routes.
- Transaction correction history, soft deletion and deterministic financial summaries.
- Explicit FNB import confirmation, account matching and transaction-level duplicate detection.
- Import history metadata. The original uploaded statement is not retained in Cloudant.
- Budget progress, goal contributions, recurring-payment candidates and per-currency summaries.
- User data export and password-confirmed account/data deletion, both with a 10,000-record-per-collection safety bound.
- Privacy audit-event listing and audit records for selected create, update, delete and import operations.
- IBM watsonx.ai chat connector using IBM IAM authentication.
- Explicit per-request AI consent for financial summaries and a separately consented, non-automatic category suggestion.
- GitHub Actions for frontend JavaScript syntax checks, strict Ruff linting, pytest, production Docker build and container smoke tests.
- Weekly Dependabot checks for Python packages and GitHub Actions.

**Implemented but gated**
- Financial account and transaction storage endpoints.
- Budget and goal storage endpoints.
- Confirmed FNB statement import and import history.
- watsonx.ai advisor chat and transaction category suggestions.

Persistent finance routes require FINANCIAL_DATA_ENABLED=true. AI routes additionally require FINANCIAL_AI_ENABLED=true and valid watsonx.ai settings. Both flags default to false. Keep them disabled until the release safeguards are complete.

**Still to complete before broader production use**
- MFA for this application and distributed rate limiting.
- A documented retention schedule and a tested, automated Cloudant backup/restore procedure.
- Full audit coverage for sensitive reads, exports, administrative actions and deletion, plus operational alerting for audit-write failures.
- Application/edge request limits, monitoring, incident response and credential rotation procedures.
- watsonx.ai project/model configuration and live integration validation.
- Privacy/security review, including the Frankfurt hosting region and cross-border processing.
- Validation against an actual FNB CSV exported by the account holder before relying on the import.

Do not treat gated or planned components as available for general use. Do not enable persistent financial data until the release checklist is signed off.

## Technology baseline

- Python 3.12, FastAPI and Uvicorn
- IBM Cloud Code Engine
- IBM Cloudant
- IBM watsonx.ai (chat connector implemented; project/model configuration required)
- IBM Cloud Object Storage (planned only if retained original statement files are required)

The architecture is a modular monolith. Separate services or Kubernetes will only be introduced if actual scaling or operational requirements justify them.

## Web application

Open /app on the deployed service. The workspace provides sign-in, FNB account metadata, FNB CSV preview and consent-based import, transaction history and correction, categories, budgets, goals, financial summaries, recurring-payment candidates, AI consent, user data export and account deletion.

The bearer access token is kept in page memory only. It is cleared when the page is reloaded or signed out. It is not stored in localStorage or sessionStorage.

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install development dependencies with: python -m pip install -r requirements-dev.txt
3. Copy .env.example to .env and configure only the values needed for the work. Never commit .env.
4. Keep FINANCIAL_DATA_ENABLED=false and FINANCIAL_AI_ENABLED=false until all release safeguards have passed.
5. Start the API with: uvicorn main:app --reload --host 127.0.0.1 --port 8080
6. Open http://127.0.0.1:8080/app for the web workspace and http://127.0.0.1:8080/docs for the API documentation.

## Finance API

All routes require authentication. Persistent finance routes also require FINANCIAL_DATA_ENABLED=true.

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
- POST /imports/fnb/pdf/preview and /imports/fnb/pdf/confirm: preview and explicitly import a validated FNB PDF against a selected, user-owned FNB account.
- /imports: view import metadata and status.

FNB imports require the account's last four digits to match the statement. The import process stores a file hash and import metadata, not the original statement. Stable transaction identifiers prevent the same transaction from being stored again when statements overlap. A completed import is bound to one user and one FNB account.

## Privacy controls

- GET /api/v1/privacy/export exports the user's application records, excluding original statement files.
- DELETE /api/v1/privacy/data requires the current password and removes the user's financial records and login account.
- Both export and deletion stop with a clear limit if a collection contains more than 10,000 records.
- GET /api/v1/privacy/audit lists available user-scoped audit events. The current audit trail covers selected data changes and imports, not every read or export.

## AI advisor

POST /api/v1/advisor/chat requires both feature gates and an explicit consent_to_share_summary=true field. It sends the question and a user-specific aggregate summary to IBM watsonx.ai. It does not send raw transaction rows, descriptions, references or account IDs.
The transaction-category suggestion route requires separate consent for one selected transaction. It sends that transaction's date, description, amount and currency plus active category names/types. The suggestion is validated and is not applied automatically.

The following IBM settings are required:
- WATSONX_APIKEY (store as a Code Engine secret)
- WATSONX_PROJECT_ID
- WATSONX_URL
- WATSONX_MODEL_ID
- WATSONX_API_VERSION

For the Frankfurt region, the current default service URL is https://eu-de.ml.cloud.ibm.com. Use the endpoint and API version shown in the Developer access page for the actual watsonx project.

## Tests and code quality

Run tests with pytest and lint with ruff check . GitHub Actions validates frontend syntax, runs strict Ruff checks and executes pytest, then builds the production Docker image and smoke-tests the container. Automated fixtures must not contain invented financial histories or example transaction amounts.

## Container build

Build with: docker build -t financial-advisor:local .
Run with: docker run --rm -p 8080:8080 --env-file .env financial-advisor:local

The container runs as a non-root user. The Dockerfile copies the same-origin frontend with the application.

## Data protection

- Never put API keys, passwords, tokens, bank statements or real financial data in GitHub, commits, tests or logs.
- Persistent financial data and AI features are disabled by default.
- Keep financial data disabled until the owner has reviewed the backup/restore limitation, validated a real FNB export, and accepted the remaining personal-use risks. Keep AI disabled until watsonx.ai is configured and validated.
- Preserve original imported transaction fields when users make corrections.
- Financial amounts must be calculated using exact decimal arithmetic. AI must not invent balances, transactions or financial metrics.
