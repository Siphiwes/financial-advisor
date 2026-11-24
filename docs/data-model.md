# Financial data model

Each Cloudant application record is namespaced by the authenticated user's UUID.

## Financial accounts

Account fields include institution, account type, user-defined display name, optional last-four-digit account suffix, currency and active status. Full account numbers, card numbers, online-banking usernames, passwords, PINs and one-time PINs are not stored.

## Transactions

Each transaction is a separate Cloudant document containing:
- account ID;
- effective transaction date;
- original description and reference from the bank export;
- signed amount (positive credit, negative debit);
- explicit ISO 4217 currency code;
- service fee and post-transaction balance when supplied;
- optional category, merchant override and notes;
- source (manual or FNB CSV);
- optional import ID, review state and deletion state.

Original source fields are preserved. User classification and notes are separate fields. Transaction deletion is a soft delete.

## Categories

Categories are owned by a user and have a name, kind (income, expense or transfer), description and active status. Users create and manage their categories.

## Budgets

A budget stores its name, calendar month in YYYY-MM format, exact amount, currency, optional category and active status. Budget progress is calculated from actual saved transactions for the selected month and currency.

## Goals and contributions

A goal stores a name, target amount, currency, optional target date and active status. Contributions are separate records with a deterministic idempotency identifier, date, amount and optional note. Displayed contributed amount is calculated from contribution records.

## Import batches

An FNB import record includes bank, source format, account ID, SHA-256 digest, upload byte count, statement date when supplied, counts and processing status. The original file contents and original filename are not retained.

A statement digest is bound to one user and one account. Reconfirming the same file for the same account returns the completed import instead of creating another batch. Transaction fingerprints also help detect repeated transaction rows across overlapping statements.

## Financial values

Money uses Decimal values with explicit currency. Binary floating point must not be used for persisted monetary calculations. Currency is recorded on each account, transaction, budget and goal.

## Ownership and querying

Every read, update and deletion operation must derive the user ID from the validated bearer token. Do not take a user ID or owner ID from client input. Scoped Cloudant document IDs do not replace ownership checks on document fields and query selectors.
