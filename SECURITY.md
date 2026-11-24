# Security policy

## Reporting a vulnerability

Do not publish credentials, personal financial information or exploitable security details in a public issue. Contact the repository owner privately through GitHub to coordinate responsible disclosure. A dedicated security contact and response process must be established before the application accepts real user financial data.

## Sensitive data rules

- Never commit live API keys, passwords, access tokens, private certificates or real bank statements.
- Use IBM Code Engine secrets for deployed credentials.
- Use synthetic financial data in development and tests.
- Do not log transaction descriptions, account identifiers, document contents or secrets.
- Rotate credentials immediately if exposure is suspected.

Authentication, authorization and multi-user isolation are not implemented yet. Do not use this prototype with real personal financial data until those controls and a privacy review are complete.
