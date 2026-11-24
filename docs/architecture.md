# Architecture

## Runtime architecture

The application is a modular monolith deployed as one FastAPI container on IBM Cloud Code Engine.

Browser UI -> FastAPI authentication and routes -> validated schemas -> application services -> Cloudant.

Optional AI flow: user consent and operator approval -> deterministic financial summary -> watsonx.ai chat completion -> response. AI does not query Cloudant directly and does not calculate authoritative figures.

## Components

- app/api/routes: authentication, statement import, finance APIs, privacy consent and advisor endpoints.
- app/schemas: validated request and response contracts.
- app/services: FNB CSV parsing and import orchestration.
- app/database: Cloudant connection and user-scoped document operations.
- app/integrations: external provider clients, currently watsonx.ai.
- app/static: same-origin browser application assets.
- tests: automated validation, security and API tests.
- docs: architecture, data model, security, deployment and operations guidance.

## Data storage

Cloudant database: finance-advisor-db.

Each application record is stored as one JSON document with:
- an ID namespaced by authenticated user ID, collection and record ID;
- user_id and type fields checked on reads;
- record_id, created_at and updated_at;
- a typed application payload under data.

Collections currently used include accounts, transactions, categories, budgets, goals, goal_contributions, imports and privacy_settings. A complete audit-event trail remains outstanding and must not be assumed complete.

A single transaction is stored per document. Statement files are not stored as Cloudant attachments or objects. Cloudant has a 1 MB JSON document limit, so an entire statement must never be placed into one document.

## Query indexes

The scoped query layer creates JSON indexes for owner/type lookups and common transaction selectors. The Cloudant service identity must have permission to create indexes as well as read/write documents. Indexes are created on first use per application process and database.

## Import architecture

1. Authenticate the user.
2. Preview the uploaded FNB CSV in memory.
3. The user selects an existing FNB account and confirms import.
4. Compute a SHA-256 digest of the exact upload bytes.
5. Create a deterministic import identifier bound to the user, account and digest.
6. Build deterministic transaction identifiers from normalized source values, preserving repeated identical rows by occurrence number.
7. Bulk-write transaction documents in bounded batches.
8. Mark the import complete, or mark it failed so a retry can continue without duplicating rows already saved for that import.

The original uploaded file is not retained. Transaction descriptions, references and amounts are stored only after explicit confirmation.

## Financial correctness

The application calculates totals, budget progress and cash flow using Decimal values from stored transaction records. Credits are positive and debits are negative. Transfers are excluded from income and expense totals when categorized as transfers. AI may explain verified aggregate figures, but must not invent or replace them.

## External AI boundary

The watsonx.ai client is optional and disabled by default. It requires the AI feature flag, operator data-processing approval, valid IBM credentials and explicit per-user consent.

Only the user's question and application-calculated aggregate summary are sent. Raw statement files, account identifiers, transaction references and descriptions are excluded.

## Deployment boundaries

The browser UI and API are same-origin, so a permissive browser CORS policy is not required. Code Engine supplies environment variables and secret references. The container runs as a non-root user.
