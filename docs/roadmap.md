# Development roadmap

This is an ordered plan, not a claim that these features already exist.

1. **Platform foundation** - modular FastAPI structure, environment template, tests, linting, CI and container hardening.
2. **Cloudant integration** - IAM authentication, database connection, least-privilege access and diagnostics.
3. **Identity and authorization foundation** - invite-only registration, Argon2id password hashing, signed short-lived access tokens, current-user validation and user-scoped document IDs.
4. **Identity lifecycle hardening** - email verification, password reset, MFA, recovery, rate limiting, session revocation and account deletion.
5. **Core finance data** - user-owned account representation, transaction schema, idempotent imports and audit history.
6. **Transaction workflows** - manual entry, CSV import, validation, duplicate detection, editing and categorization.
7. **Finance calculations** - income/expense summaries, cash flow, budgets, recurring payments and financial goals.
8. **AI assistance** - watsonx.ai integration for classification suggestions, explanations and question answering grounded in verified application data.
9. **Statement processing** - secure upload, object storage, extraction, validation, user review and deletion controls.
10. **Production readiness** - privacy review, threat modelling, monitoring, backups, recovery tests, operational cost review and security testing.

Each phase should have acceptance criteria, automated tests and a working deployment before the next phase begins. Do not import real financial records until all required protections are in place.
