# Privacy and financial data handling

The application is intended to work with user-authorized real bank exports. The current finance persistence routes are disabled by default using FINANCIAL_DATA_ENABLED=false.

## Data categories and purpose

The current model may contain account metadata, transaction dates, descriptions, references, amounts, currencies, bank-provided balance values, categories, budgets, goals and import metadata. Each field must serve a documented feature. Do not collect online banking credentials, PINs or card security codes.

## User control

Before persistent real-data use, provide clear user information covering:
- What information is collected and why.
- How a user can access, correct, export and delete records.
- Retention periods and deletion handling.
- Who can access data and how privileged access is audited.
- Whether any information is sent to IBM watsonx.ai or another external provider.
- The account holder's consent and how it can be withdrawn.

## Storage and processing

- The current IBM Cloud deployment target is Frankfurt, Germany.
- Review cross-border processing and transfer arrangements before onboarding users or processing financial data beyond controlled owner testing.
- The FNB CSV import stores transaction records and a file hash, not the original uploaded statement.
- Do not write statement contents, transaction descriptions, account identifiers or credentials to application logs.
- Financial records are namespaced by user ID. All new API operations must retain this boundary.

## Release blockers

Before enabling FINANCIAL_DATA_ENABLED:
- Define and implement retention periods and user deletion/export.
- Configure automated backups and test restoration.
- Add audit events for sensitive data operations without recording financial payloads.
- Define incident response and access-review procedures.
- Complete a privacy and security assessment, including applicable South African POPIA obligations and cross-border transfer requirements.

This document is an engineering checklist, not a legal opinion or POPIA compliance certification. Obtain qualified review before onboarding other users.
