# Security baseline

## Secrets

- Never commit live API keys, passwords, access tokens or private certificates.
- Use local `.env` files only for local development; they are ignored by Git and excluded from Docker build context.
- Use IBM Code Engine secrets for deployed credentials.
- Keep Cloudant diagnostics credentials separate from application credentials.
- Keep `JWT_SECRET_KEY` and `AUTH_EMAIL_INDEX_KEY` independent, random, and at least 32 bytes long.
- Keep `REGISTRATION_INVITE_CODE` private. Registration is disabled when it is not configured.
- Rotate credentials if exposed. Do not paste secrets into issues, logs or chat.

## Financial data protection

- Do not commit bank statements, transaction exports, account identifiers or personal financial records to GitHub.
- Do not import actual financial data until authentication, per-user authorization, consent, retention, deletion, backup and access controls are implemented and tested.
- Automated tests use technical fixtures and mocked service responses, not fabricated financial transaction histories.
- End-to-end finance tests should use user-authorized actual financial records only after the required protections are in place.
- Collect only the data required for a defined feature.
- Do not log transaction descriptions, account identifiers, document contents, API keys or authentication tokens.

## Authentication currently implemented

- Account registration requires the `X-Registration-Invite` header and a server-side `REGISTRATION_INVITE_CODE`. If the secret is absent, registration is disabled.
- Passwords are hashed using Argon2id through pwdlib. Passwords are never returned by API responses.
- Access tokens are signed JWTs using HS256, with issuer, audience, expiry, subject, token ID and account-version claims.
- Access-token lifetime is constrained to 5-60 minutes and defaults to 15 minutes.
- The current-user dependency reloads the account from Cloudant and checks account status and token version on every protected request.
- User email lookup document IDs use a keyed HMAC. Raw email addresses are stored only in the user document, not in its Cloudant document ID.
- Financial document IDs include the authenticated user's UUID namespace. Access helpers require the caller's user ID and do not accept an owner ID from request payloads.

## Important limitations before real financial data

- Authentication endpoints are a foundation, not a complete production identity platform.
- There is no password reset, verified-email workflow, MFA, refresh-token rotation, account recovery or user-facing session revocation endpoint yet.
- Registration invite codes are a bootstrap control, not a substitute for a full onboarding and abuse-prevention workflow.
- Apply edge-level rate limiting to registration and login before public exposure.
- Configure a strong, unique JWT secret and email-index key in Code Engine before enabling registration or issuing tokens.
- Do not expose finance endpoints until every read, update, delete, export and aggregate query is tied to the authenticated user and has cross-user isolation tests.
- Complete privacy, retention, deletion, backup, restore, audit logging and incident-response controls before importing real bank data.

## AI safety and financial correctness

- Treat imported documents and transaction descriptions as untrusted input.
- Do not let document text or model output execute code, queries or privileged actions.
- Validate model outputs against schemas and deterministic calculations.
- Clearly distinguish verified figures, estimates and AI-generated explanations.
- Do not present the application as a licensed financial adviser or imply guaranteed outcomes.

## Deployment

Run the container as a non-root user. Keep dependencies reviewed and updated. Restrict CORS to known frontend origins when a browser frontend is introduced.


## FNB statement preview

- FNB CSV uploads are accepted only by an authenticated preview endpoint.
- The uploaded file is parsed in memory and is not written to Cloudant.
- The API limits CSV uploads to 5 MB and transaction rows to 10,000.
- Account numbers are reduced to their last four digits in preview metadata.
- The preview returns at most 10 transaction rows.
- Do not log uploaded file contents, transaction descriptions, references or account identifiers.
- Persistent statement and transaction imports remain disabled until consent, deduplication, ownership enforcement, retention, deletion, backup and restore, and audit controls are implemented and verified.
