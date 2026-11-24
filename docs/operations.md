# Operations checklist

## Current API operation

- Confirm the Code Engine revision is Ready after deployment.
- Check application logs for startup errors. Never log credentials, transaction descriptions, account identifiers or financial document contents.
- Smoke-test /, /health and /docs.
- Test authentication and verify that protected endpoints reject unauthenticated requests.
- Keep FINANCIAL_DATA_ENABLED=false until the release checklist is complete.
- Review IBM Cloud service usage, quotas and costs.

## Before enabling financial data

- Complete retention, correction, user export and deletion workflows.
- Configure automated Cloudant backups and test a restoration into a controlled recovery environment.
- Record security audit events without logging financial payloads.
- Set request size, rate and timeout limits at the application and edge layers.
- Establish monitoring and alerts for authentication failures, import errors, Cloudant failures and application availability.
- Define credential rotation, incident response and user notification processes.
- Review privacy, consent and applicable South African legal requirements, including cross-border processing.

## Import operations

- Confirm each FNB import is tied to the correct user-owned account.
- Check import status and duplicate counts.
- Do not store original bank files unless a separate retention and deletion design is approved.
- Investigate partial imports before retrying. Deterministic transaction IDs are intended to make retries safe.
- Keep raw statement contents out of tickets, source control and logs.

## Deployment

- Build from the reviewed main commit.
- Verify the image digest and Code Engine revision.
- Confirm environment variables and secret references without printing secret values.
- Verify readiness, health and API documentation.
- Test account isolation and feature-gate behaviour after every release.
