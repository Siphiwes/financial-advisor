# Privacy and data handling

This document describes current application behavior and remaining privacy work. It is not legal advice or a POPIA compliance certification.

## Data collected

After a user confirms an FNB import, the application stores normalized transaction information: effective date, original description and reference, signed amount, currency, service fee and balance when supplied. It stores an account reference and an optional last-four-digit account suffix.

The original uploaded CSV file and original filename are not retained. The application does not request or store FNB usernames, passwords, PINs or one-time PINs.

## Access and user controls

Accounts, transactions, categories, budgets, goals and import records are stored under the authenticated user's namespace. Finance routes derive the user identity from the validated access token, not from a user-supplied owner ID.

Transactions can be soft-deleted. Complete account export, complete account deletion and a formal retention schedule are still required before broader production use.

## Optional AI processing

The AI advisor is disabled by default. It requires operator approval and affirmative per-user consent.

When enabled, the user's question and application-calculated aggregate income, expenses, cash flow and category totals are sent to IBM watsonx.ai. Raw statement files, account numbers, transaction descriptions and references are not included in the AI request.

Users can withdraw consent through the privacy settings endpoint. The operator must verify the selected watsonx.ai service region, model, contract, data retention, subprocessors and data-processing terms before enabling AI.

## Storage location and cross-border processing

The current IBM Cloud environment is in Frankfurt. The operator must assess POPIA requirements for processing and transfers outside South Africa, including section 72, and confirm the applicable lawful basis, safeguards and contractual commitments.

## Outstanding privacy controls

A complete retention schedule, audit evidence, backup and restore plan, user export/deletion process and incident response procedure remain required before onboarding other users' financial records.
