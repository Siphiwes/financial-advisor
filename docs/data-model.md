# Data model planning

This document records design areas to settle before implementing persistence. It is not a deployed schema.

## Planned concepts

- User: identity and preferences. Authentication provider and user identifier strategy are still to be selected.
- Financial account: a user-owned account representation. Avoid storing bank login credentials.
- Transaction: amount, currency, transaction date, description, merchant, category, account reference, source/import reference and review status.
- Category: system category plus optional user-defined categories and correction history.
- Budget: period, category or envelope, planned amount and currency.
- Financial goal: target amount, target date, contribution history and status.
- Import batch: source, processing status, file reference, deduplication metadata and audit timestamps.

## Financial data rules

- Store monetary values as integer minor units or exact decimal values, never binary floating point.
- Store currency explicitly using ISO 4217 codes. The initial user market is South Africa, but do not assume every transaction is ZAR.
- Preserve original source values where needed for audit and user correction.
- Store timestamps consistently in UTC and preserve the transaction's local date where relevant.
- Define ownership and access checks before any user data is persisted.
- Define duplicate detection and correction history before bulk imports are enabled.

A detailed Cloudant document design, indexes and partitioning strategy will be decided with the first persistence feature, based on actual query patterns.
