# Development roadmap

The roadmap separates implemented backend capabilities from the remaining first-release work.

1. **Platform and Cloudant foundation - implemented.** FastAPI, Code Engine deployment baseline, Cloudant IAM connection, protected diagnostics, container hardening and CI.
2. **Identity foundation - implemented.** Invite-only registration, Argon2id password hashing, signed short-lived access tokens, current-user validation and user-scoped document IDs.
3. **FNB CSV intake - implemented.** Authenticated preview, 20 MB limit, FNB field parsing and explicit confirmation endpoint.
4. **Core financial records - backend implementation added.** User-owned account metadata, transaction create/read/update/soft-delete, transaction correction history, categories, budgets, goals and per-currency financial summaries. Persistent routes remain disabled by default pending release safeguards.
5. **Import reliability - backend implementation added.** Account matching, file hash metadata, deterministic transaction identifiers and duplicate handling for overlapping statements.
6. **Financial workflows - remaining.** Budget-versus-actual calculations, savings-goal contributions, recurring-payment detection, richer categorisation and exports.
7. **Identity lifecycle hardening - remaining.** Email verification, password reset, MFA, recovery, rate limiting, session revocation and account deletion.
8. **AI assistance - remaining.** watsonx.ai integration for grounded categorisation suggestions, explanations and question answering, plus prompt-injection controls and cost limits.
9. **User interface - remaining.** Web frontend for authentication, statement upload/review, transactions, budgets, goals, dashboard and AI advisor.
10. **Production readiness - remaining.** Retention/deletion, backup and restore, audit logging, monitoring, incident response, privacy/security review and release runbook.

A successful build or deployment does not establish production readiness. Do not enable persistent real financial data until the safeguards in docs/security.md, docs/privacy.md and docs/operations.md have been completed and verified.
