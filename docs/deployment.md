# Deployment notes

## Target

The API and same-origin web workspace are deployed as one application to IBM Cloud Code Engine in Frankfurt. The container listens on port 8080 and starts with uvicorn main:app.

- Web workspace: /app
- API documentation: /docs
- Liveness: /health

## Configuration and secrets

Use Code Engine secrets for credentials and environment references for non-secret settings. Do not bake credentials into the image or pass them as Docker build arguments.

Existing Cloudant settings:
- CLOUDANT_URL: preferred HTTPS endpoint.
- CLOUDANT_API_KEY: IAM API key from the Cloudant Writer service credential.
- CLOUDANT_DATABASE: defaults to finance-advisor-db.
- CLOUDANT_DIAGNOSTICS_TOKEN: optional separate secret for temporary protected diagnostics. Leave its application reference absent after connectivity verification.

Authentication settings:
- JWT_SECRET_KEY
- AUTH_EMAIL_INDEX_KEY
- REGISTRATION_INVITE_CODE (only when enabling invite-only registration)
- ACCESS_TOKEN_EXPIRE_MINUTES

Financial data:
- FINANCIAL_DATA_ENABLED=false by default.
- Keep it false until backup/restore, retention, deletion, audit, monitoring, incident-response and privacy release controls have passed review.
- Setting it to true enables authenticated account, transaction, category, budget, goal, analytics and confirmed FNB import routes.

AI advisor:
- FINANCIAL_AI_ENABLED=false by default. The AI route also requires FINANCIAL_DATA_ENABLED=true.
- WATSONX_APIKEY: store as a Code Engine secret. Do not expose it to the browser or source control.
- WATSONX_PROJECT_ID: the actual IBM watsonx project ID.
- WATSONX_URL: regional watsonx.ai Runtime endpoint. Frankfurt default: https://eu-de.ml.cloud.ibm.com.
- WATSONX_MODEL_ID: a chat-capable model available to the selected project.
- WATSONX_API_VERSION: API version date currently supported for the selected Runtime endpoint.

The API obtains an IBM IAM bearer token from the API key and caches it in application memory until shortly before expiry. It calls POST /ml/v1/text/chat?version=....

The advisor route requires explicit per-request consent. The chat route sends the user's question plus aggregated income, expense, transfer, cash-flow and category totals for the selected date range. The category-suggestion route separately sends one selected transaction's date, description, amount and currency plus the active category names/types, only after a distinct consent action. Neither route sends account identifiers, references or statement files. Prompts and responses are not persisted.

Before enabling the AI feature, verify the actual project ID, model ID, API version, model permissions and regional endpoint using the IBM watsonx Developer access page.

## FNB import behaviour

- POST /imports/fnb/csv/preview parses a statement for review and does not persist it.
- POST /imports/fnb/csv/confirm requires authentication, explicit confirmation, an account selected from the current user's records and a matching last-four-digit check.
- The confirmed import stores transactions and import metadata. It does not store the original uploaded statement.
- The same file/account import is idempotent. Transaction hashes prevent overlapping statements from duplicating transactions.
- CSV size is limited to 20 MB; parser transaction count is limited to 10,000.

## Diagnostics

- GET /health/cloudant checks IAM authentication and read access.
- POST /diagnostics/cloudant/round-trip creates, reads and deletes a temporary non-financial probe.
- Both endpoints require X-Cloudant-Diagnostics-Token.
- Keep the diagnostics token reference absent after the connectivity test so these endpoints remain disabled.

## Release sequence

1. Review the commit and dependency changes.
2. Confirm GitHub Actions frontend syntax, strict Ruff and pytest checks passed.
3. Build the image from the reviewed main commit.
4. Verify the image digest and deploy a new Code Engine revision.
5. Confirm the revision is Ready and test /app, /, /health and /docs.
6. Verify authentication and user isolation.
7. Verify FINANCIAL_DATA_ENABLED and FINANCIAL_AI_ENABLED remain false unless their respective release gates are signed off.
8. Test Cloudant connectivity only through the temporary diagnostics procedure, then remove the diagnostics token reference.
9. Enable external AI processing only after per-request consent wording, data minimization and IBM project configuration have been verified.

A successful container deployment does not prove that finance data safeguards are complete or that a real statement has been parsed correctly.


## Release runbook

Use docs/release-checklist.md before building the production image. It records the existing IBM Cloud resources, required secret references, feature-gate approvals, build steps, smoke checks, real FNB statement validation and rollback procedure.
