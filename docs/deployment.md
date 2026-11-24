# Deployment notes

## Current target

The API is deployed to IBM Cloud Code Engine in Frankfurt. The container listens on port 8080 and starts with `uvicorn main:app`.

## Configuration

Use Code Engine secrets for credentials and environment references for non-secret settings. Do not bake credentials into the image or pass them as Docker build arguments.

Current Cloudant secret references were configured in Code Engine. The application does not yet consume them; Cloudant client code and a connectivity check are a later implementation step.

## Release sequence

1. Run lint and automated tests in GitHub Actions.
2. Review the commit and dependency changes.
3. Build the container from the repository's root Dockerfile.
4. Deploy a new Code Engine revision.
5. Verify the revision is Ready.
6. Smoke-test `/` and `/health`.
7. Test provider connectivity only after that integration has been implemented.

Do not assume a successful container deployment proves that an external service connection works.
