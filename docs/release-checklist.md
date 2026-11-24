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

## 4. Feature gates

The defaults are intentionally safe:

- FINANCIAL_DATA_ENABLED=false
- FINANCIAL_AI_ENABLED=false

The application, login and preview interface can be smoke-tested while these flags are false. Persistent account/transaction/budget/goal APIs and confirmed FNB imports remain disabled until the financial-data release approval is complete.

Before setting FINANCIAL_DATA_ENABLED=true, complete all of the following:
- [ ] Define retention periods and deletion handling for primary data and backups.
- [ ] Configure automated Cloudant backups, protect backup access and complete a restore test.
- [ ] Verify user export and password-confirmed account deletion, including the 10,000-record-per-collection limit.
- [ ] Expand audit coverage to sensitive reads, exports, account deletion and administrative operations; set alerts for audit-write failures.
- [ ] Configure distributed rate limiting and abuse protection for registration, login, imports and AI.
- [ ] Complete the required identity lifecycle controls for the intended audience, including email verification, password reset, MFA and account recovery, or document an approved restricted owner-only operating model.
- [ ] Establish monitoring, incident response, credential rotation and an access-review process.
- [ ] Complete the privacy/security assessment, including POPIA and the Frankfurt cross-border processing arrangements.

Do not set FINANCIAL_DATA_ENABLED=true simply to make a deployment smoke test pass.

Keep FINANCIAL_AI_ENABLED=false until the IBM watsonx.ai project, model, region, credentials, retention terms, user notice and data-sharing approval are all verified. AI requests also require explicit user consent.

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
