# Security baseline

## Secrets

- Never commit live API keys, passwords, access tokens, bank statements or private certificates.
- Use IBM Code Engine secrets for deployed credentials and local .env files for development only.
- Keep JWT_SECRET_KEY and AUTH_EMAIL_INDEX_KEY independent, random and at least 32 bytes long.
- Keep REGISTRATION_INVITE_CODE private. Registration is disabled if it is not configured.
- Store the watsonx.ai API key as a Code Engine secret.
- Rotate credentials immediately if exposure is suspected.

## Authentication and authorization

- Passwords are hashed using Argon2id.
- Access tokens are signed JWTs with issuer, audience, expiry, subject, token ID and account-version claims.
- Protected routes reload the active user from Cloudant.
- Finance document IDs include the authenticated user's UUID namespace.
- Stored user ID, document type and record ID are verified on reads.
- List queries include the authenticated user ID and collection type, and returned records are checked again.
- Never accept an owner ID from request input.
- The browser holds the access token in memory only. It does not store it in localStorage or sessionStorage.

## Financial data

- Original imported transaction date, description, reference, amount, currency, fee and balance are preserved.
- Classification, merchant overrides and notes are stored separately from original bank fields.
- Original FNB CSV files are parsed in memory and are not retained.
- Confirmed imports save one transaction per Cloudant document and a statement digest/import record.
- Statement and transaction identifiers are deterministic so retries can be detected.
- Financial calculations use Decimal values, not binary floating point.
- Do not log transaction descriptions, account identifiers, statement contents, API keys or authentication tokens.

## Upload and browser protections

- FNB CSV upload limit is 20 MB and transaction count limit is 10,000.
- Upload endpoints require authentication.
- Persistence requires a separate confirmation request.
- Account number suffixes are masked to the final four digits in the preview.
- The browser app is served same-origin with a restrictive Content Security Policy, frame protection, MIME sniffing protection, referrer policy and permissions policy.
- All user-controlled values rendered by the browser must be HTML-escaped.

## AI controls

- watsonx.ai is disabled by default.
- Both AI_ADVISOR_ENABLED and AI_DATA_PROCESSING_APPROVED must be true.
- Each user must separately consent to external AI processing.
- Only the user's question and application-calculated aggregate figures are sent. Raw statements, account numbers, references and transaction descriptions are excluded.
- The model is instructed not to invent or replace financial figures.
- AI output is educational and must not be represented as regulated financial advice.

## Remaining production controls

- Email verification, password reset, recovery and MFA.
- Distributed rate limiting and abuse protection.
- Complete audit trail for sensitive actions, reads, exports and deletion.
- User export and complete account deletion.
- Backup/restore testing, incident response and credential-rotation procedures.
- Threat model, security review, dependency scanning and POPIA/cross-border processing assessment.

Do not onboard other users' real financial information until the remaining controls have been implemented and reviewed.
