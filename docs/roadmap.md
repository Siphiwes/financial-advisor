# Development roadmap

This is an ordered plan, not a claim that these features already exist.

1. **Platform foundation** - modular FastAPI structure, environment template, tests, linting, CI and container hardening.
2. **Cloudant integration** - IAM authentication, connection lifecycle, least-privilege access, repository layer and connectivity/readiness checks.
3. **Core finance data** - user model, account representation, transaction schema, idempotent imports and audit history.
4. **Transaction workflows** - manual entry, CSV import, validation, duplicate detection, editing and categorization.
5. **Finance calculations** - income/expense summaries, cash flow, budgets, recurring payments and financial goals.
6. **AI assistance** - watsonx.ai integration for classification suggestions, explanations and question answering grounded in verified application data.
7. **Statement processing** - secure upload, object storage, extraction, validation, user review and deletion controls.
8. **User experience and notifications** - frontend, authentication, alerts and reports.
9. **Production readiness** - privacy review, threat modelling, monitoring, backups, recovery tests, rate limiting and operational cost review.

Each phase should have acceptance criteria, automated tests and a working deployment before the next phase begins.
