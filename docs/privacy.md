# Privacy and financial data handling

The application is designed to work with user-authorized real bank exports. Persistent finance routes are disabled by default using FINANCIAL_DATA_ENABLED=false. This document is an engineering checklist, not a legal opinion or POPIA compliance certification.

## Data categories and purpose

The current model may contain account metadata, transaction dates, descriptions, references, amounts, currencies, bank-provided balance values, categories, budgets, goals and import metadata. Each field must serve a documented feature. Do not collect online banking credentials, PINs or card security codes.

The original uploaded FNB CSV is parsed in memory and is not retained. A SHA-256 digest and import metadata are stored after confirmation, alongside normalized transaction records. Account metadata stores the last four digits only.

## User control

The application implements authenticated data export and password-confirmed account/data deletion. Transactions can be corrected while retaining original values and correction history, or soft-deleted. Export and deletion are bounded at 10,000 records per collection; original statement files are not included because they are not retained.

Before persistent real-data use, provide clear user information covering:
- What information is collected and why.
- How a user can access, correct, export and delete records.
- Retention periods and deletion handling, including backup retention.
- Who can access data and how privileged access is audited.
- Whether any information is sent to external AI providers, what fields are shared, and the applicable provider terms.
- The account holder's consent and how it can be withdrawn.

## AI processing

The AI advisor is separately disabled by default. Each AI request requires a consent flag. When chat consent is given, the backend sends the user's question and an aggregated financial summary to IBM watsonx.ai. The summary includes currency-level income, expenses, transfers, net cash flow, expense totals by category and the selected date range.

A separate category-suggestion action requires its own consent and sends only the selected transaction's date, description, amount and currency plus the allowed category names/types. Account IDs, references and uploaded statement files are excluded. The question and response are not stored by the current endpoints.

AI processing must remain disabled until the user-facing notice, provider configuration, data-sharing terms and applicable privacy review have been completed.

## Storage and processing

- The current IBM Cloud deployment target is Frankfurt, Germany.
- Review cross-border processing and transfer arrangements before onboarding users or processing financial data beyond controlled owner testing.
- Do not write statement contents, transaction descriptions, account identifiers or credentials to application logs.
- Financial records are namespaced by user ID. All new API operations must retain this boundary.

## Release blockers

Before enabling FINANCIAL_DATA_ENABLED:
- Define retention periods and deletion handling for production data and backup copies.
- Configure automated Cloudant backups and test restoration.
- Expand audit events to cover sensitive reads, exports, account deletion and administrative actions, and alert on audit-write failures.
- Define incident response and access-review procedures.
- Complete a privacy and security assessment, including applicable South African POPIA obligations and cross-border transfer requirements.

Obtain qualified legal and privacy review before onboarding other users.
