# Financial data model

This document describes the current Cloudant document model. It is not a claim that production retention, backup or compliance controls are complete.

## Ownership and document IDs

Each financial document ID uses this namespace:

finance:{normalized-user-uuid}:{collection}:{record-uuid}

The authenticated user ID is derived from the validated access token and Cloudant user record. Finance API request bodies do not accept an owner ID. Reads, writes and deletes are performed within the authenticated user's namespace.

## Collections

### Accounts

- Institution (initially FNB)
- User-selected display name
- Account type
- ISO 4217 currency
- Last four account-number digits only
- Active/inactive status

Online banking passwords, PINs, card security codes and full account numbers are not stored.

### Transactions

- Account reference
- Transaction date
- Original description and reference
- Signed amount (positive inflow, negative outflow)
- Currency
- Service fee and balance-after values where supplied by the bank
- User category and notes
- Source (manual or fnb_csv)
- Import ID, where applicable
- Original imported fields
- Correction history
- Soft-deletion status

Monetary values are stored as decimal strings and parsed into Decimal for calculations. Never use binary floating-point for money.

### Import batches

- Source and selected account ID
- SHA-256 hash of the uploaded file
- Processing status
- Statement date, where supplied
- Parsed transaction count, imported count and duplicate count
- Started and completed timestamps

The raw statement file is not persisted by the current import endpoint. The file hash is metadata, not a retrievable statement copy.

### Categories, budgets and goals

Categories include built-in values and user-defined values. Budgets record a category, currency, amount, period and date range. Goals record a target, currency, optional target date and user-entered saved amount.

## FNB duplicate detection

The import batch identifier is derived from the authenticated user, selected account and uploaded file hash. Transaction identifiers are deterministic hashes of the selected account and source transaction fields. Re-importing the same file can return the existing completed batch; overlapping statements skip transactions already present for that account.

## Financial calculation rules

- Currency is explicit for every account and transaction. Amounts in different currencies are never added together.
- Income is represented by positive transaction amounts; expenses are negative.
- The summary API returns income, expenses and net cash flow per currency.
- Only expenses are grouped into category spending totals.
- A bank balance is not inferred from an incomplete transaction range. The application may display a bank-provided balance-after value only where the statement supplies one.
