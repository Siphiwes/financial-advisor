# FNB statement import

## First supported format

The first supported input is the FNB South Africa transaction-history CSV export. The parser recognizes these transaction fields:

- Effective Date
- Description
- Reference
- Service Fee
- Debit / Credit indicator for the service fee, where present
- Amount
- Balance

Amounts are parsed as decimal values, not binary floating-point numbers. A leading or trailing minus sign is treated as a debit. The service-fee debit/credit indicator is applied separately from the transaction amount.

## Preview endpoint

POST /imports/fnb/csv/preview

The endpoint requires a valid bearer access token and accepts a multipart upload with a .csv filename.

The preview:
- validates the FNB transaction columns;
- parses the statement in memory;
- returns statement metadata and all validated transaction rows (up to 10,000);
- masks the account number to its last four digits;
- rejects files larger than 20 MB or containing more than 10,000 transaction rows.

The endpoint does not write the uploaded statement or transaction data to Cloudant. It does not retain the original file. Do not place statement contents, transaction descriptions or account identifiers in logs.

## Getting the file from FNB

In FNB Online Banking, open My Bank Accounts, select the relevant account, open Transaction History, then use the download option and select CSV when available. The exact menu labels can differ between profile types.

FNB also supports other transaction-history exports, including PDF, QIF, OFC and OFX. Those formats are not enabled by this first preview endpoint.

## Before persistent import is enabled

Persistent storage of real bank data remains disabled at this stage. Before that feature is added, implement and verify transaction-level ownership checks, duplicate handling, user consent, retention and deletion controls, backup and restore, audit logging, and safe exports. Validate the parser against an actual FNB CSV exported by the account holder before enabling storage.
