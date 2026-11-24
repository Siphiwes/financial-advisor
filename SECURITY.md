# Security policy

## Reporting a vulnerability

Do not publish credentials, personal financial information or exploitable security details in a public issue. Contact the repository owner privately through GitHub to coordinate responsible disclosure. A dedicated security contact and response process must be established before the application accepts other users' real financial data.

## Sensitive data rules

- Never commit live API keys, passwords, access tokens, private certificates or real bank statements.
- Use IBM Code Engine secrets for deployed credentials.
- Do not log transaction descriptions, account identifiers, document contents or secrets.
- Rotate credentials immediately if exposure is suspected.
- Never request or store FNB online-banking passwords, PINs or one-time PINs.

## Current security controls

- Invite-only registration with Argon2id password hashing.
- Short-lived signed JWT access tokens and active-user checks on protected routes.
- User-scoped Cloudant document IDs and owner/type checks on list and read operations.
- Authenticated FNB preview and explicit confirmation before persistence.
- No retention of original FNB CSV files.
- Browser security headers and in-memory access-token handling.
- watsonx.ai disabled by default, requiring operator approval and individual consent.

## Remaining security work

Email verification, password reset, account recovery, MFA, distributed rate limiting, comprehensive audit logging, user export/deletion, backup/restore testing, incident response and a POPIA/cross-border processing review remain before broader production use.

Do not onboard other users' real financial information until these controls have been implemented and reviewed.
