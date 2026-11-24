# Security baseline

## Secrets

- Never commit live API keys, passwords, access tokens or private certificates.
- Use local `.env` files only for development; they are ignored by Git and excluded from Docker build context.
- Use IBM Code Engine secrets for deployed credentials.
- Rotate credentials if exposed. Do not paste secrets into issues, logs or chat.

## Data protection

- Use synthetic data during development and automated tests.
- Collect only data needed for a defined feature.
- Define consent, retention, deletion, backup and access controls before accepting real bank statements or personal financial information.
- Do not log transaction descriptions, account identifiers, document contents, API keys or authentication tokens.

## Authorization

Authentication and authorization are not implemented yet. Before multi-user or real financial data is introduced, enforce user-level access controls at every data access boundary and test for cross-user data exposure.

## AI safety and financial correctness

- Treat imported documents and transaction descriptions as untrusted input.
- Do not let document text or model output execute code, queries or privileged actions.
- Validate model outputs against schemas and deterministic calculations.
- Clearly distinguish confirmed figures, estimates and AI-generated explanations.
- Do not present the application as a licensed financial adviser or imply guaranteed outcomes.

## Deployment

Run the container as a non-root user. Keep dependencies updated and review dependency/security alerts. Restrict CORS to known frontend origins when a browser frontend is introduced.
