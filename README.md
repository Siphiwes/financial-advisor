# AI Personal Finance Advisor

A South Africa-focused personal finance application built around user-authorized financial records. The first bank import workflow supports First National Bank (FNB) transaction-history CSV exports.

## Implemented in the current release branch

- FastAPI application and responsive browser interface served from one container.
- IBM Cloudant IAM connection and user-scoped data access.
- Invite-only registration, Argon2id password hashing and short-lived JWT access tokens.
- Authenticated financial account, transaction, category, budget and goal APIs.
- FNB CSV preview and separate user-confirmed import with a 20 MB upload limit.
- Statement digest, deterministic transaction identifiers and retry-aware import processing.
- Financial summaries and budget progress calculated by application code.
- Goal contributions with idempotency keys.
- Optional IBM watsonx.ai integration behind operator approval and per-user consent.
- GitHub Actions CI for Ruff linting and pytest.

The imported CSV file is parsed in memory and is not retained. After confirmation, normalized transaction records and statement digest/import metadata are saved in Cloudant. The application does not request or store FNB online-banking credentials, PINs or one-time PINs.

## Important release limitations

This is the first application release, not a certification of production readiness. Before accepting other users' real financial records, complete email verification, password recovery, MFA, distributed rate limiting, a full audit trail, user export and deletion, backup/restore testing, incident response and a POPIA/cross-border processing review.

The AI advisor is disabled by default. It must not be enabled until the operator has approved the relevant IBM watsonx.ai data-processing arrangements and users have actively consented. The AI receives the user's question and application-calculated aggregates only, not raw statements or transaction descriptions.

The importer still requires validation against an actual FNB CSV exported by the account holder before relying on it for financial decisions.

## Technology

- Python 3.12, FastAPI and Uvicorn
- IBM Cloud Code Engine
- IBM Cloudant
- IBM watsonx.ai (optional, disabled by default)
- Static HTML, CSS and JavaScript

The application is a modular monolith. It uses one API container and one Cloudant database. The current workflow does not retain original statement files, so IBM Cloud Object Storage is not required for FNB imports at this stage.

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install development dependencies:

       python -m pip install -r requirements-dev.txt

3. Copy .env.example to .env and configure only the services required for development. Never commit .env.
4. Start the API:

       uvicorn main:app --reload --host 127.0.0.1 --port 8080

5. Open http://127.0.0.1:8080/ for the application and /docs for API documentation.

## Main API areas

- /auth: invite-only registration, login and current-user identity.
- /api/v1/accounts: user-owned financial account references.
- /api/v1/transactions: transaction creation, search, classification and soft deletion.
- /api/v1/categories: user-defined income, expense and transfer categories.
- /api/v1/budgets: budgets and budget progress.
- /api/v1/goals: financial goals and idempotent contributions.
- /api/v1/analytics: deterministic financial summaries.
- /imports/fnb/csv: FNB CSV preview, confirmation and import history.
- /api/v1/privacy/ai-consent and /api/v1/advisor/ask: privacy-controlled AI assistance.

## Data protection

- Never commit bank statements, transactions, account numbers, credentials or access tokens to GitHub.
- Financial account records store an optional last-four-digit suffix only.
- Original statement files are not retained. Confirmed transaction records are stored separately under the authenticated user's namespace.
- Every finance query must derive ownership from the authenticated user identity.
- Financial calculations use Decimal. AI is not authoritative for balances, totals or financial metrics.
