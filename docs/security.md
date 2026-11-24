# Security baseline

## Secrets

- Never commit live API keys, passwords, access tokens or private certificates.
- Use local `.env` files only for local development; they are ignored by Git and excluded from Docker build context.
- Use IBM Code Engine secrets for deployed credentials.
- Keep the Cloudant diagnostics token separate from the Cloudant IAM API key.
- Rotate credentials if exposed. Do not paste secrets into issues, logs or chat.

## Financial data protection

- Do not commit bank statements, transaction exports, account identifiers or personal financial records to GitHub.
- Do not import actual financial data until user authentication, per-user authorization, consent, retention, deletion, backup and access controls are implemented and tested.
- Automated tests may use isolated technical fixtures and mocked service responses. They must not introduce fabricated financial transaction histories as product test data.
- End-to-end finance tests should use user-authorized actual financial records only after the required protections are in place.
- Collect only the data required for a defined feature.
- Do not log transaction descriptions, account identifiers, document contents, API keys or authentication tokens.

## Authorization

Authentication and authorization are not implemented yet. Before real financial data is introduced, enforce user-level access controls at every data access boundary and test for cross-user data exposure.

## AI safety and financial correctness

- Treat imported documents and transaction descriptions as untrusted input.
- Do not let document text or model output execute code, queries or privileged actions.
- Validate model outputs against schemas and deterministic calculations.
- Clearly distinguish verified figures, estimates and AI-generated explanations.
- Do not present the application as a licensed financial adviser or imply guaranteed outcomes.

## Deployment

Run the container as a non-root user. Keep dependencies reviewed and updated. Restrict CORS to known frontend origins when a browser frontend is introduced.
