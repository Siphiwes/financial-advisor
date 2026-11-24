# Security policy

## Reporting a vulnerability

Do not publish credentials, personal financial information or exploitable security details in a public issue. Contact the repository owner privately through GitHub to coordinate responsible disclosure. Establish a dedicated security contact and response process before onboarding other users.

## Sensitive data rules

- Never commit live API keys, passwords, access tokens, private certificates or real bank statements.
- Use IBM Code Engine secrets for deployed credentials.
- Do not put real financial records in tests, issues or commit history.
- Do not log transaction descriptions, account identifiers, document contents or secrets.
- Rotate credentials immediately if exposure is suspected.

Authentication and owner-scoped finance persistence foundations are implemented. Persistent finance endpoints are disabled by default using FINANCIAL_DATA_ENABLED=false.

Do not enable persistent real financial data for general use until retention, deletion, export, tested backups and restoration, audit logging, incident response, identity lifecycle controls and privacy/security review are complete. See docs/security.md for the release blockers.
