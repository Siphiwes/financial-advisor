# Deployment notes

## Current target

The API is deployed to IBM Cloud Code Engine in Frankfurt. The container listens on port 8080 and starts with `uvicorn main:app`.

## Configuration

Use Code Engine secrets for credentials and environment references for non-secret settings. Do not bake credentials into the image or pass them as Docker build arguments.

The application reads these Cloudant settings:

- `CLOUDANT_URL`: the preferred HTTPS endpoint for the Cloudant instance.
- `CLOUDANT_API_KEY`: the IAM API key from the Cloudant Writer service credential.
- `CLOUDANT_DATABASE`: database name; defaults to `finance-advisor-db`.
- `CLOUDANT_DIAGNOSTICS_TOKEN`: separate secret required for the protected diagnostic endpoints.

The current Cloudant secret references provide the URL and IAM API key. Add the diagnostics token as a separate key in the Code Engine secret and reference it as an application environment variable before using the diagnostic endpoints.

## Cloudant diagnostics

- `GET /health/cloudant` checks IAM authentication and read access to the configured database.
- `POST /diagnostics/cloudant/round-trip` creates a short-lived technical probe document, reads it back, and deletes it.
- Both endpoints require the `X-Cloudant-Diagnostics-Token` header.
- The diagnostic probe contains no financial data. Do not expose the diagnostics token or include it in source control.
- Remove the `CLOUDANT_DIAGNOSTICS_TOKEN` application reference after the connectivity test is complete. The diagnostic endpoints will then remain disabled.

## Release sequence

1. Run lint and automated tests in GitHub Actions.
2. Review the commit and dependency changes.
3. Build the container from the repository's root Dockerfile.
4. Deploy a new Code Engine revision.
5. Verify the revision is Ready.
6. Smoke-test `/` and `/health`.
7. Configure the diagnostics token and test Cloudant access.
8. Remove the diagnostics token reference after verification.

Do not assume a successful container deployment proves that an external service connection works.
