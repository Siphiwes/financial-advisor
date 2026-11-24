# AI Personal Finance Advisor

An AI-powered personal finance application designed initially for South African users. The system will help users understand transactions, spending, budgets, cash flow and financial goals, with AI-assisted explanations based on verified financial data.

## Current implementation status

**Implemented**
- FastAPI application.
- Root information endpoint: `GET /`.
- Liveness endpoint: `GET /health`.
- IBM Cloud Code Engine container deployment.
- IBM Cloudant Lite instance and `finance-advisor-db` database provisioned.
- Cloudant SDK dependency declared.

**Not yet implemented**
- Live Cloudant connection and persistence.
- User authentication and authorization.
- Transaction import and categorization.
- watsonx.ai integration.
- Document processing and financial analytics.

The documentation describes planned foundations as well as implemented functionality. Do not treat planned components as working features.

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
  database/         Database access and persistence
  integrations/     External provider clients (Cloudant, watsonx, IBM COS)
  models/           Domain and persistence models
  schemas/          API request and response schemas
  services/         Application and business logic
tests/              Automated tests
docs/               Architecture, security and delivery documentation
.github/workflows/  Continuous integration
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

5. Open:
   - API: http://127.0.0.1:8080/
   - Health: http://127.0.0.1:8080/health
   - Interactive API docs: http://127.0.0.1:8080/docs

The application loads a local `.env` file for development. In IBM Cloud, configure environment values through Code Engine secrets and configuration, not through a file inside the image.

## Tests and code quality

Run tests:

```bash
pytest
```

Run lint checks:

```bash
ruff check .
```

GitHub Actions runs these checks on pushes and pull requests to `main`.

## Container build

```bash
docker build -t financial-advisor:local .
docker run --rm -p 8080:8080 --env-file .env financial-advisor:local
```

The container runs as a non-root user. Docker build exclusions are maintained in `.dockerignore`.

## Configuration and secrets

- `.env.example` documents configuration names only. It contains no live credentials.
- Local `.env` files are ignored by Git and excluded from Docker build context.
- IBM Cloud credentials must be stored in IBM Cloud Code Engine secrets.
- Do not place API keys, passwords, tokens, bank statements or real financial data in GitHub issues, commits, tests or logs.

## Project documentation

- [Architecture](docs/architecture.md)
- [Security baseline](docs/security.md)
- [Development roadmap](docs/roadmap.md)

## Financial correctness

Financial amounts must be calculated by deterministic application logic using verified transaction data. An AI model may explain or contextualize calculated results, but must not invent balances, transactions or financial metrics. Estimates and predictions must be labelled separately from confirmed figures.
