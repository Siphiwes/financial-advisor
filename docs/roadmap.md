# Release roadmap

## Implemented in the release branch

1. FastAPI modular application, container and CI foundation.
2. Cloudant IAM connection, user-scoped document namespaces and scoped query indexes.
3. Invite-only registration, Argon2id password hashing, signed short-lived access tokens and current-user validation.
4. User-owned financial accounts, transaction APIs, categories, budgets and financial goals.
5. FNB CSV preview and user-confirmed transaction import.
6. Deterministic financial summary and budget-progress calculations.
7. Responsive same-origin browser application.
8. watsonx.ai integration behind operator approval and per-user consent.

## Remaining before broader production use

1. Email verification, password reset, account recovery and MFA.
2. Distributed login, registration, import and AI rate limiting.
3. Complete append-only audit events for sensitive access, exports, updates and deletions.
4. User data export and complete account deletion workflow.
5. Backup, restore and disaster-recovery procedures with an executed restore test.
6. Security review, threat model, dependency scanning and incident response.
7. POPIA privacy review, cross-border transfer review and applicable agreements with IBM and other processors.
8. Validate the importer against an actual FNB CSV supplied by the account holder before relying on imported figures.
9. Verify watsonx.ai model availability, region, project permissions, costs, retention and data-processing terms before enabling AI.
10. Decide whether original statement retention is required. It is not enabled in this release. If later required, implement private object storage, encryption, retention and deletion separately.

## Release rule

Do not deploy a branch simply because it builds. Require passing CI, review the changed files and dependencies, verify IBM resource configuration, deploy once and complete the documented smoke checks. Do not import other users' real financial records until the remaining protections have been completed.
