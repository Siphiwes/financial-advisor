# First-release readiness checklist

This checklist is the deployment gate for the first complete release. A feature existing in the repository does not mean it has been enabled or accepted for production use.

## Current implementation in the repository

- FastAPI API and same-origin web workspace at /app.
- Invite-only registration, login, current-user validation and Cloudant user records.
- Argon2id password hashing, password change and account-wide token revocation after password verification.
- Cloudant owner-scoped financial records.
- FNB CSV preview (20 MB limit, maximum 10,000 parsed rows).
- FNB import confirmation with explicit consent, user-selected account, last-four-digit match, import history, file hash and deterministic transaction identifiers.
- Accounts, transactions, correction history, soft deletion, categories, budgets, budget progress, goals, goal contributions and deterministic per-currency analytics.
- Recurring-payment candidates derived from the user's saved transaction history.
- Consent-based watsonx.ai financial question answering using aggregated figures.
- Consent-based single-transaction category suggestions. Suggestions are validated against the user's category list and are not applied automatically.
- User data export, password-confirmed deletion and retryable account deletion.
- User-scoped minimal audit events for financial record creation, update and FNB import.
- Security response headers and no-store caching for private API responses.
- CI checks for JavaScript syntax, strict Ruff linting and pytest.

## Default feature switches

Keep both switches disabled until all release gates below pass:

- FINANCIAL_DATA_ENABLED=false
- FINANCIAL_AI_ENABLED=false

The AI switch also depends on the financial data switch. The FNB preview and authentication routes can be used while persistent financial data remains disabled.

## External IBM configuration required before the one-time deployment

### Cloudant

- Confirm the existing Cloudant service credential still has the required access to finance-advisor-db.
- Keep the API key in a Code Engine secret, not in GitHub.
- Confirm the database name and HTTPS service URL in Code Engine.
- Do not re-enable the temporary Cloudant diagnostics token after connectivity testing.

### IBM Cloud Object Storage and backups

Cloudant account data is not yet protected by a configured, tested backup-and-restore process in this repository. Before real transaction records are stored:

- Provision a private backup bucket in an approved IBM Cloud region.
- Configure encryption, least-privilege credentials and restricted administrative access.
- Implement automated, versioned backups with integrity verification.
- Set a defined retention period and lifecycle expiry.
- Test restoring a backup into a separate recovery database.
- Test the restore procedure together with the user-deletion policy. A deleted account must not be unintentionally reintroduced by a later restore.
- Document recovery point and recovery time objectives, owners and escalation steps.

Do not set FINANCIAL_DATA_ENABLED=true until the backup and restore process has been executed successfully, not merely configured.

### watsonx.ai

The connector is implemented, but live provider connectivity has not been verified against the user's project. Before enabling AI:

- Configure WATSONX_APIKEY as a Code Engine secret.
- Configure WATSONX_PROJECT_ID, WATSONX_URL, WATSONX_MODEL_ID and WATSONX_API_VERSION.
- Confirm that the project can access the selected chat model in the Frankfurt region.
- Test IAM token acquisition and chat inference with non-sensitive operational content.
- Test the consent flow and inspect the exact data payload sent by the server.
- Review the IBM service terms, model data handling and retention for the intended use.

Keep FINANCIAL_AI_ENABLED=false until those checks pass.

## Remaining application and security work

The repository has working foundations for account and data controls, but these items remain incomplete or require a production review:

- Email verification and verified-email change.
- Email-based password recovery and account recovery.
- Multi-factor authentication.
- Registration/login rate limiting and automated abuse protection at the edge.
- Durable, tamper-resistant audit logging and alerting. The current Cloudant audit events are best-effort.
- User export and deletion for accounts exceeding 10,000 records per collection. The current API returns a controlled limit error for larger accounts.
- A formal retention schedule, deletion procedure and backup expiry policy.
- Monitoring, alerting, incident response, credential rotation and access reviews.
- A complete privacy/security review, including South African POPIA obligations and cross-border processing because the current Cloudant and Code Engine region is Frankfurt.
- A product and financial-calculation review covering transfers, reversals, fees, pending transactions, multiple accounts and multiple currencies.
- Browser acceptance testing on desktop and mobile, accessibility review and secure error handling.

## FNB validation requirements

The parser currently supports the FNB CSV layout only. It has not yet been validated against an actual FNB export from the account holder.

Before the one-time release:

1. Obtain the actual CSV through FNB Online Banking. Never place it in GitHub, email tickets or this chat.
2. Validate it using the authenticated preview endpoint in the application.
3. Compare the parsed dates, descriptions, references, service fees, debit/credit values and balances against the source statement.
4. Check the account-last-four match against the selected account.
5. Confirm how the specific export represents reversals, transfers, pending transactions, fees, duplicate-looking rows and statement summary lines.
6. Only after backup/restore and privacy controls pass should persistent import be enabled and the account holder confirm the import.

The preview currently displays only the first 10 rows. The import confirmation processes the full validated file. For a production release, provide a way for the account holder to inspect all rows or download a complete parsed preview before confirming a large statement.

PDF, OFX, QIF and direct FNB Open Banking integration are not implemented in this release.

## Financial correctness acceptance criteria

- Currency is stored for every account and transaction; different currencies are never combined.
- Monetary values use decimal strings and Decimal calculations.
- Imported source fields remain preserved when a user corrects a transaction.
- Duplicate import retries do not silently create duplicate records.
- Transfers are reported separately from income and expenses.
- Budgets use transactions in the selected currency, category and period.
- Goals change only through explicit user-entered contributions or withdrawals.
- Recurring-payment detection produces candidates, not confirmed subscriptions.
- AI never writes balances or transaction details and never applies categories without user confirmation.
- AI only receives data that the user explicitly approved for that individual request.

## One-time deployment sequence

Once the external resources, actual FNB validation, security/privacy review and CI are ready:

1. Freeze and review the final main commit.
2. Confirm GitHub Actions has passed frontend syntax, Ruff and pytest for that exact commit.
3. Configure all Code Engine secrets and environment variables without exposing their values.
4. Set feature switches deliberately. Do not enable finance or AI gates until their separate acceptance criteria pass.
5. Build one immutable container image from the reviewed commit.
6. Record the image digest and deploy one Code Engine revision.
7. Verify /, /health, /docs and /app.
8. Verify registration/login, current-user, password change and session revocation.
9. Verify Cloudant access, owner isolation, export, deletion and backup restore.
10. Validate the actual FNB CSV and then perform an explicitly confirmed import.
11. Verify analytics against the saved bank records before enabling AI features.
12. Enable watsonx.ai only after its separate provider and consent tests pass.

A successful container deployment is not evidence that backups, restoration, privacy obligations, FNB parser compatibility or AI configuration are complete.
