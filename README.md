# AI Personal Finance Advisor

An AI-powered personal finance application designed initially for South African users. The system will help users understand transactions, spending, budgets, cash flow and financial goals, with AI-assisted explanations based on verified financial data.

## Current implementation status

**Implemented**
- FastAPI application and IBM Cloud Code Engine deployment.
- IBM Cloudant IAM connection and protected connectivity diagnostics.
- Invite-only account registration with Argon2id password hashing.
- Short-lived signed JWT access tokens.
- Authenticated current-user endpoint.
- Cloudant helpers that namespace finance records by authenticated user ID.
- Automated tests and GitHub Actions lint/test workflow.

**Not yet implemented**
- Full production identity lifecycle (email verification, password reset, MFA and recovery).
- Finance account and transaction APIs.
- Secure bank statement import and document storage.
- Transaction categorization and financial analytics.
- watsonx.ai integration.

Do not treat planned components as working functionality. Authentication must be configured and deployed before registration can be used.

## Technology baseline

- Python 3.12
- FastAPI and Uvicorn
- IBM Cloud Code Engine
- IBM Cloudant
- IBM watsonx.ai (planned)
- IBM Cloud Object Storage (planned for document storage)

The initial architecture is a modular monolith. Separate services or Kubernetes will only be introduced if actual scaling or operational requirements justify them.

## Repository structure

```text
app/
  api/routes/       HTTP endpoints
  core/             Application configuration and shared concerns
  database/         Cloudant access and persistence
  integrations/     External provider clients
  models/            Domain and persistence models
  schemas/           API request and response validation
  services/          Application and business logic
tests/               Automated tests
docs/                Architecture, security and delivery documentation
.github/workflows/   Continuous integration
```

## Local development

1. Create and activate a Python 3.12 virtual environment.
2. Install development dependencies:

   ```bash
   python -m pip install -r requirements-dev.txt
   ```

3. Copy `.env.example` to `.env` and fill in only the values needed for the feature being developed. Never commit `.env`.
4. Start the API:

   ```bash
   uvicorn main:app --reload --host 127.0.0.1 --port 8080
   ```

5. Open the API at http://127.0.0.1:8080/ and interactive docs at http://127.0.0.1:8080/docs.

## Authentication API

- `POST /auth/register`: invite-only registration. Requires the `X-Registration-Invite` header.
- `POST /auth/token`: exchange email and password for a short-lived bearer token.
- `GET /auth/me`: return the authenticated account. Requires `Authorization: Bearer <token>`.

Required server-side settings: `JWT_SECRET_KEY`, `AUTH_EMAIL_INDEX_KEY`, and (to enable registration) `REGISTRATION_INVITE_CODE`. Keep the two cryptographic keys independent and at least 32 bytes long. Do not put their values in source control.

## Tests and code quality

Run tests with `pytest` and lint with `ruff check .`. GitHub Actions runs both on pushes and pull requests to `main`.

## Container build

```bash
docker build -t financial-advisor:local .
docker run --rm -p 8080:8080 --env-file .env financial-advisor:local
```

The container runs as a non-root user. Docker build exclusions are maintained in `.dockerignore`.

## Data protection

- Do not put API keys, passwords, tokens, bank statements or real financial data in GitHub issues, commits, tests or logs.
- Do not import real bank records until user-level authorization, retention, deletion, backup, restore and access controls have been reviewed and tested.
- Financial amounts must be calculated by deterministic application logic. AI may explain verified results but must not invent balances, transactions or financial metrics.
