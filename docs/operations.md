# Operations checklist

## Current API operation

- Confirm the Code Engine revision is Ready after deployment.
- Check application logs for startup errors. Never log credentials, transaction descriptions, account identifiers or financial document contents.
- Smoke-test /, /health, /app, /docs and static frontend assets.
- Test authentication and verify that protected endpoints reject unauthenticated requests.
- Keep FINANCIAL_DATA_ENABLED=false until the release checklist is complete.
- Keep FINANCIAL_AI_ENABLED=false until the IBM project/model and data-sharing review are complete.
- Review IBM Cloud service usage, quotas and costs.

## Before enabling financial data

- Verify transaction correction, user export and password-confirmed account deletion, including the documented 10,000-record-per-collection bound.
- Define retention periods and deletion handling for primary data and backups.
- Configure automated Cloudant backups and test a restoration into a controlled recovery environment.
- Expand audit events to cover sensitive reads, exports, account deletion and administrative actions. Alert when audit writes fail.
- Set request size, rate and timeout limits at the application and edge layers.
- Establish monitoring and alerts for authentication failures, import errors, Cloudant failures, audit-write failures and application availability.
- Define credential rotation, incident response and user notification processes.
- Review privacy, consent and applicable South African legal requirements, including cross-border processing.

## Import operations

- Confirm each FNB import is tied to the correct user-owned account.
- Check import status and duplicate counts.
- Do not store original bank files unless a separate retention and deletion design is approved.
- Investigate partial imports before retrying. Deterministic transaction IDs are intended to make retries safe.
- Validate the parser against an actual FNB export supplied by the account holder before treating import results as reconciled.
- Keep raw statement contents out of tickets, source control and logs.

## Deployment

- Build from the reviewed main commit.
- Verify the image digest and Code Engine revision.
- Confirm environment variables and secret references without printing secret values.
- Verify readiness, health, web workspace, API docs and static asset delivery.
- Test account isolation and feature-gate behaviour after every release.


## Cloudant backup and recovery

Use docs/backup-recovery.md and scripts/cloudant-backup.sh / scripts/cloudant-restore.sh. Run backup jobs only in a protected runner with secrets injected at runtime. The application container does not perform backups.

- [ ] Create the COS bucket and dedicated HMAC service credential.
- [ ] Generate and securely escrow an age identity; backup runners use only the public recipient.
- [ ] Set CLOUDANT_URL, CLOUDANT_API_KEY, CLOUDANT_DATABASE, AGE_RECIPIENT, COS_BUCKET, COS_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_DEFAULT_REGION in the protected runner.
- [ ] Run a backup and confirm encrypted object and checksum are uploaded.
- [ ] Create a new empty Cloudant recovery database.
- [ ] Restore using AGE_IDENTITY_FILE, BACKUP_OBJECT and RESTORE_DATABASE.
- [ ] Verify document counts, authentication, user isolation and database security settings.
- [ ] Approve recovery time and data-loss objectives.
- [ ] Configure COS lifecycle only after retention approval.

The scripts are tooling, not evidence that a scheduled backup or restore has run. Do not mark the backup requirement complete until the restore test has succeeded.
