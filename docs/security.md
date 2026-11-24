# Security baseline

## Secrets

- Never commit live API keys, passwords, access tokens or private certificates.
- Use local .env files only for development; they are ignored by Git and excluded from the Docker build context.
- Use IBM Code Engine secrets for deployed credentials.
- Keep Cloudant diagnostics credentials separate from application credentials.
- Keep JWT_SECRET_KEY and AUTH_EMAIL_INDEX_KEY independent, random and at least 32 bytes long.
- Keep REGISTRATION_INVITE_CODE private. Registration is disabled when it is not configured.
- Store WATSONX_APIKEY only as a Code Engine secret.
- Rotate credentials if exposed. Do not paste secrets into issues, logs or chat.

## Authentication implemented

- Account registration requires X-Registration-Invite and a server-side REGISTRATION_INVITE_CODE. If the secret is absent, registration is disabled.
- Passwords are hashed using Argon2id through pwdlib. Passwords are never returned by API responses.
- Access tokens use HS256 JWT signatures, issuer, audience, expiry, subject, token ID and account-version claims.
- Access-token lifetime is constrained to 5-60 minutes and defaults to 15 minutes.
- The current-user dependency reloads the account from Cloudant and checks account status and token version on every protected request.
- User email lookup document IDs use a keyed HMAC. Raw email addresses are stored only in the user document, not in its Cloudant document ID.

## Financial data safeguards implemented

- Finance records use user-scoped Cloudant document IDs and authenticated user IDs.
- Account, transaction, category, budget, goal, import and analytics routes require a valid authenticated user.
- FINANCIAL_DATA_ENABLED defaults to false. Persistent finance endpoints return HTTP 503 until the flag is deliberately enabled.
- FNB statement preview is authenticated and does not persist statement or transaction contents.
- FNB confirmation requires explicit consent, an existing user-owned FNB account and a last-four-digit account match.
- The original uploaded statement is not stored. The import stores a SHA-256 file hash and import metadata.
- Stable transaction identifiers provide retry-safe duplicate detection across overlapping statements.
- Transaction corrections preserve the originally imported values and record before/after changes.
- Amounts use decimal strings in storage and Decimal calculations.

## AI data handling

- FINANCIAL_AI_ENABLED defaults to false and the AI route also requires FINANCIAL_DATA_ENABLED.
- The AI route requires explicit per-request consent before calling IBM watsonx.ai.
- Only the user's question and an aggregate summary of income, expenses, transfers, cash flow, category totals and date range are sent.
- Raw transaction rows, transaction descriptions, references, account IDs and uploaded statement files are excluded.
- The current chat route does not persist questions or responses.
- Never place secrets or financial information in provider error logs.
- Review provider region, project permissions, retention and applicable contractual/privacy terms before enabling this integration.

## Remaining release blockers

Do not set FINANCIAL_DATA_ENABLED=true for general use until these items are implemented and verified:
- User-facing data export and deletion, including related import metadata.
- Explicit retention periods and deletion schedules.
- Automated backups, access controls for backups and a tested restoration procedure.
- Audit events for account, transaction, import and administrative operations.
- Rate limiting and abuse controls for registration and login.
- Email verification, password reset, MFA, account recovery and session revocation.
- Operational monitoring, incident response and credential rotation procedures.
- Privacy and security review, including the hosting region and any cross-border data processing.

## FNB import constraints

- The CSV upload limit is 20 MB and the parser limits a statement to 10,000 transactions.
- Only the account's last four digits are retained in account metadata.
- Statement descriptions and references are financial personal information. Never log them.
- Treat every bank-export field as untrusted input.
- The current FNB parser supports the FNB CSV layout only. Validate it against the account holder's actual export before enabling persistent imports.

## AI safety and financial correctness

- Transaction descriptions and imported documents are untrusted content.
- Do not let document text or model output execute code, queries or privileged actions.
- Validate model output against schemas and deterministic calculations.
- Clearly distinguish verified figures, estimates and AI-generated explanations.
- Do not present the application as a licensed financial adviser or imply guaranteed outcomes.

## Deployment

Run the container as a non-root user. Restrict CORS to known frontend origins when a browser frontend is introduced. Keep diagnostics disabled when the temporary diagnostics token is not configured.
