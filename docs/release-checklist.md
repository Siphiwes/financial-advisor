# One-time first-release deployment checklist

This checklist is the release runbook for the first complete application deployment to IBM Cloud Code Engine. Complete every required item before starting the build. Do not change secrets or enable financial-data features halfway through the deployment.

## 1. GitHub release verification

- [ ] Confirm the intended release is merged into main.
- [ ] Confirm the latest main workflow passed all stages: frontend JavaScript syntax, Ruff, pytest, production Docker build and container smoke test.
- [ ] Confirm the build uses the root Dockerfile and that app/static is included in the image.
- [ ] Confirm no bank statements, actual transactions, account numbers, passwords, PINs, API keys or access tokens are in GitHub.
- [ ] Confirm Dependabot is enabled for Python dependencies and GitHub Actions.
- [ ] Record the exact main commit SHA and keep it with the release record.

## 2. IBM Cloud resources

Use the existing Frankfurt resources. Do not create a second Cloudant database or Code Engine application for this release.

- Code Engine project: Financial-Advisor-Dev.
- Code Engine application: Financial Advisor API.
- Existing build configuration: financial-advisor-app-build-p2vxm.
- Container registry/image: private.de.icr.io/finance-advisor-app/finance-advisor.
- Cloudant instance: Financial-advisor-cloudant.
- Cloudant database: finance-advisor-db.
- Cloudant service identity: existing Writer credential.

Check that the Cloudant application credential can read, create, update and delete documents, use bulk document writes, and read documents by ID. The current scoped query/import implementation does not depend on a new Mango index.

## 3. Code Engine secret references

Verify references only. Do not paste secret values into GitHub, logs, tickets or chat.

Existing Cloudant secret cloudant-api-secret:
- CLOUDANT_URL
- CLOUDANT_API_KEY

Existing authentication secret financial-advisor-auth-secret:
- JWT_SECRET_KEY
- AUTH_EMAIL_INDEX_KEY
- REGISTRATION_INVITE_CODE

Confirm:
- JWT_SECRET_KEY and AUTH_EMAIL_INDEX_KEY are independent random secrets of at least 32 bytes.
- The registration invitation code is private and only shared with intended account holders.
- CLOUDANT_DIAGNOSTICS_TOKEN is not referenced by the application after connectivity testing.
- No secret values are stored in image build arguments or plain environment variables.

## 4. Feature gates for personal use

The defaults remain disabled:

- FINANCIAL_DATA_ENABLED=false
- FINANCIAL_AI_ENABLED=false

This deployment is intended for one owner, not public registration or commercial multi-user access. Keep registration invitation-only and do not share the application publicly.

Before enabling FINANCIAL_DATA_ENABLED for personal use:
- [ ] Confirm the owner can sign in and the account email is verified.
- [ ] Confirm the real FNB CSV preview matches the source statement before the first import.
- [ ] Confirm export and account deletion endpoints are available.
- [ ] Understand that automated backup and restore are intentionally out of scope. Cloudant data loss or accidental deletion may be permanent.
- [ ] Keep credentials and financial records out of GitHub, logs and email.

The owner has explicitly deferred MFA, a separate security-testing phase, Redis provisioning, backup/restore work and a formal POPIA/commercial compliance review. Do not present those controls as completed.

Keep FINANCIAL_AI_ENABLED=false until the existing IBM watsonx.ai integration has the correct Frankfurt project, model ID, API version and credentials. Keep explicit per-request consent enabled. Do not send raw bank statements or full transaction histories to the AI provider.

## 5. Build and deploy

Only start this section after the applicable feature-gate decisions have been signed off.

1. Open the existing Code Engine build configuration financial-advisor-app-build-p2vxm.
2. Confirm source repository Siphiwes/financial-advisor, branch main, and root Dockerfile.
3. Confirm the existing destination image private.de.icr.io/finance-advisor-app/finance-advisor.
4. Build the image once from the recorded main commit.
5. Confirm the build succeeded and record the image digest.
6. Deploy that image to the existing Financial Advisor API application.
7. Confirm the new revision is Ready and receives traffic.
8. Do not remove the previous known-good revision until post-deployment verification is complete.

The CI workflow has already built and smoke-tested the production container. The Code Engine build/deployment verifies the separate IBM Cloud environment and its secret references.

## 6. Post-deployment smoke checks

- [ ] GET /health returns healthy.
- [ ] GET /app loads the web workspace.
- [ ] /assets/app.js and the stylesheet load successfully.
- [ ] /docs displays the API documentation.
- [ ] Sign in with the existing account.
- [ ] GET /auth/me returns the signed-in account.
- [ ] Unauthenticated finance and import routes return 401.
- [ ] With FINANCIAL_DATA_ENABLED=false, persistent finance routes and import confirmation return 503.
- [ ] FNB CSV preview works only for an authenticated user and does not persist the uploaded statement.
- [ ] AI routes remain disabled while FINANCIAL_AI_ENABLED=false.
- [ ] Cloudant diagnostics remain disabled because the temporary diagnostics token is not configured.

## 7. Validate the real FNB export

Use a CSV downloaded directly by the account holder from FNB Online Banking. Do not use a fabricated example file.

Before confirming an import, compare the preview with the original statement:
- Statement date and account last-four digits.
- Transaction count.
- Effective dates.
- Original descriptions and references.
- Debit/credit signs and exact amounts.
- Service fees and their indicators.
- Post-transaction balances.

The selected FNB account's last four digits must match the statement. Review the preview first. Confirm only after the source fields match. The original CSV is not retained; normalized transaction records and a file hash/import record are stored after confirmation.

Repeat the same file/account import only as an idempotency check. It should return the existing completed import rather than creating another copy.

## 8. Rollback

- Keep the previous known-good Code Engine revision available until verification is complete.
- If the container fails its health or UI checks, restore traffic to the previous revision.
- Do not delete, recreate or overwrite the Cloudant database as a rollback method.
- Keep the existing secret references unchanged during a code rollback.
- Investigate failed or partial imports before retrying. Deterministic IDs are intended to prevent duplicate transaction documents.

## Release rule

The application can be deployed with financial and AI features disabled for a safe technical smoke test. A deployment with persistent financial data enabled is approved only after the operational and privacy controls above have been completed and verified. This checklist does not replace a legal review or a real-statement validation.


## 9. Recovery and audit implementation status

Repository support is now present:
- scripts/cloudant-backup.sh streams a full CouchBackup export through gzip and age encryption before uploading the encrypted object and checksum to COS.
- scripts/cloudant-restore.sh verifies the downloaded checksum, decrypts the archive and restores only to a separately named database.
- CI syntax-checks both shell scripts.
- Sensitive finance reads, statement preview/history, export and AI data-sharing requests write minimal audit events. Required audit writes fail closed.

Still requires IBM Cloud/operator action:
- Provision COS bucket and least-privilege HMAC credentials.
- Generate and securely escrow the age private identity.
- Configure protected scheduled execution and alerting.
- Run a real backup and restore into a new empty Cloudant database.
- Recreate Cloudant security settings and validate the restored application in an isolated environment.
- Complete and approve docs/retention-policy-template.md, including COS lifecycle expiry.
- Decide RPO and RTO and document evidence.

The audit collection is user-scoped and is deleted with the account. It is not an immutable compliance archive. Audit coverage is improved but does not yet include every authentication, administrative, export/deletion or operational event. Do not describe this as complete compliance audit logging.


## Shared rate-limit service

The application now supports Redis-backed authentication rate limits, but the limiter is disabled by default.

- [ ] Provision a private Redis-compatible service with TLS.
- [ ] Store REDIS_URL in a Code Engine secret and reference it in the application.
- [ ] Set APP_ENV=production and AUTH_RATE_LIMIT_ENABLED=true.
- [ ] Confirm Code Engine's observed socket peer behavior before relying on peer-based limits; do not trust arbitrary X-Forwarded-For headers.
- [ ] Verify HTTP 429 and Retry-After behavior across multiple application instances.
- [ ] Verify the app fails closed with HTTP 503 if the shared store is unavailable.

Do not enable public registration or broader user access before this has been verified.


## Personal-use transactional email

- [ ] Configure a personal SMTP provider using TLS (port 465 or STARTTLS on 587).
- [ ] Store the SMTP app password in an IBM Code Engine secret.
- [ ] Set the SMTP environment variables and the deployed HTTPS APP_PUBLIC_URL.
- [ ] Send and receive a real verification email.
- [ ] Keep EMAIL_ENABLED=false until delivery succeeds.
- [ ] Keep registration invitation-only. Do not enable public sign-up.

See docs/transactional-email.md for the personal Gmail SMTP setup and account workflow details.
