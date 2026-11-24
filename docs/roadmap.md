# Development roadmap

The roadmap separates implemented backend capabilities from remaining first-release readiness work.

1. **Platform and Cloudant foundation - implemented.** FastAPI, Code Engine deployment baseline, Cloudant IAM connection, protected diagnostics, container hardening, strict linting, unit/API tests, Docker build and container smoke tests.
2. **Identity foundation - implemented.** Invite-only registration, Argon2id password hashing, signed short-lived access tokens, current-user validation, password change, all-session revocation and user-scoped document IDs.
3. **FNB CSV intake - implemented.** Authenticated preview, 20 MB limit, FNB field parsing, explicit confirmation, account last-four matching, import metadata and deterministic transaction duplicate detection. Original statement files are not retained.
4. **Core financial records - implemented behind a feature gate.** User-owned account metadata, transaction create/read/update/soft-delete, transaction correction history, categories, budgets, goals, goal contributions and per-currency financial summaries.
5. **Financial workflows - implemented behind a feature gate.** Budget progress, savings-goal contributions/withdrawals, recurring-payment candidates and transaction category correction.
6. **Privacy controls - implemented with bounds.** User data export, password-confirmed account/data deletion and user-scoped audit-event listing. Export and deletion stop when a collection exceeds 10,000 records.
7. **AI assistance - connector implemented, configuration pending.** watsonx.ai chat, explicitly consented aggregate summaries, separately consented transaction category suggestions and validation that suggestions are not automatically applied. The model/project configuration and live integration validation remain.
8. **User interface - implemented.** Same-origin web workspace for authentication, account metadata, FNB preview/import, transactions, budgets, goals, financial summaries, privacy controls and AI features.
9. **Identity lifecycle hardening - remaining.** Email verification, password reset, MFA, account recovery and distributed rate limiting. Password change and session revocation are implemented.
10. **Production readiness - remaining.** Retention schedule, automated backup and tested restore, complete audit coverage, audit failure alerting, operational monitoring, incident response, application/edge rate limits, privacy/security review and cross-border processing assessment.

Persistent finance storage is disabled by default through FINANCIAL_DATA_ENABLED=false. AI is separately disabled through FINANCIAL_AI_ENABLED=false. Do not enable either until the safeguards in docs/security.md, docs/privacy.md and docs/operations.md have been completed and verified.

A successful build, passing CI or a healthy deployment does not establish financial-data correctness or production readiness. Validate the FNB parser against an actual statement exported by the account holder before importing real transactions.
