# FNB statement import

## Supported format

The first supported bank import is the FNB South Africa transaction-history CSV export. The parser recognizes the FNB transaction columns: Effective Date, Description, Reference, Service Fee, fee debit/credit indicator, Amount and Balance.

Money values are parsed as Decimal. A minus sign on the transaction amount is treated as a debit. The parser supports UTF-8 with or without BOM and Windows-1252 text encoding.

## User flow

1. In FNB Online Banking, open My Bank Accounts, select the account, open Transaction History and download CSV.
2. Sign in to the Personal Finance Advisor.
3. Add the matching FNB account reference. The account record stores an optional last-four-digit suffix, not the full account number.
4. Upload the CSV to POST /imports/fnb/csv/preview.
5. Review the statement date, account suffix, transaction count and preview rows.
6. Confirm the import using POST /imports/fnb/csv/confirm, passing the selected account ID and the same CSV.

Preview parses in memory and does not persist transaction rows. Confirmation saves normalized transaction records to Cloudant under the signed-in user's namespace.

## Data retained

The application stores original date, description, reference, amount, currency, service fee and balance where supplied by FNB. User classification, merchant override and notes are separate fields. The original CSV bytes and original filename are not retained.

A SHA-256 digest identifies the exact uploaded file. The import ID is bound to the user and selected FNB account. Transaction identifiers are deterministic and account for repeated identical rows in one statement. Repeating the same file for the same account returns the existing completed import. Overlapping statement exports can skip matching transaction fingerprints already stored.

If a bulk write partially succeeds, the import is marked failed. A retry can identify transactions already written for that import and continue without creating another copy of them.

## Limits and safeguards

- Maximum upload size: 20 MB.
- Maximum transaction rows: 10,000.
- Preview response: up to 10 rows.
- Account suffix: final four digits only.
- Authentication is required for preview and confirmation.
- The application never asks for FNB login credentials, PINs or one-time PINs.
- Statement account suffix is compared with the selected account suffix when both are available.
- Imported monetary values exceeding 16 whole digits or two decimal places are rejected instead of silently rounded.

## Validation before relying on the import

Validate the parser against an actual FNB CSV exported by the account holder. Compare dates, descriptions, references, debit/credit signs, service fees and balances with the original export. Do not treat the import as reconciled until the source values have been checked.
