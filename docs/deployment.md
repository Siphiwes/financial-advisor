# Deployment notes

## Target

The application is deployed to IBM Cloud Code Engine in Frankfurt. The container listens on port 8080 and starts with uvicorn main:app. The browser UI and API are served from the same origin.

## Required Code Engine configuration

Use the existing secrets and environment references. Do not put secret values in the repository or build arguments.

Cloudant:
- CLOUDANT_URL
- CLOUDANT_API_KEY
- CLOUDANT_DATABASE=finance-advisor-db

Authentication:
- JWT_SECRET_KEY
- AUTH_EMAIL_INDEX_KEY
- REGISTRATION_INVITE_CODE
- ACCESS_TOKEN_EXPIRE_MINUTES=15
- JWT_ALGORITHM=HS256

Keep the separate CLOUDANT_DIAGNOSTICS_TOKEN reference removed after the earlier connectivity test. Do not re-enable diagnostic endpoints for normal use.

Optional AI configuration:
- WATSONX_APIKEY
- WATSONX_PROJECT_ID
- WATSONX_URL
- WATSONX_MODEL_ID
- WATSONX_API_VERSION=2024-05-31
- AI_ADVISOR_ENABLED=false
- AI_DATA_PROCESSING_APPROVED=false

Keep both AI flags false until the operator has verified the IBM watsonx.ai region, contract, retention, security and data-processing arrangements. Per-user consent is also required.

## Build and release sequence

1. Merge the reviewed release branch into main only after GitHub Actions passes.
2. Confirm the main commit contains the complete release and all documentation.
3. Start the existing Code Engine build configuration from main.
4. Confirm the build uses the current root Dockerfile and registry image.
5. Deploy a new Code Engine revision using the new image.
6. Confirm the revision is Ready and receives traffic.
7. Smoke-test the browser UI, /health, /docs, login and /auth/me.
8. Verify Cloudant queries and indexes using the configured application service identity.
9. Add an FNB account reference, preview an actual statement, inspect its values and only then confirm import.
10. Keep the AI advisor disabled unless its separate approval process is complete.

Do not assume a successful container build proves Cloudant operations, import correctness, or external AI processing.

## Deployment safeguards

The first deployment of the release must not run a migration that deletes, rewrites or reclassifies existing user documents. Index creation is additive. Confirm that the Cloudant service credential can create the required JSON indexes before deployment.

The deployment process does not require a new Cloudant instance, database, JWT key or invitation secret. Keep the existing credentials unless a deliberate rotation is planned.
