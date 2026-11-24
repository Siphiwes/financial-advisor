# Cloudant backup and recovery runbook

## Scope and limitations

IBM Cloudant's supported CouchBackup utility exports database documents through the Cloudant API and restores them to a new, empty database. It does not back up Cloudant database security settings or attachments. Original FNB statement files are intentionally not retained.

References:
- IBM Cloudant backup and recovery: https://cloud.ibm.com/docs/Cloudant?topic=Cloudant-ibm-cloudant-backup-and-recovery
- CouchBackup project and limitations: https://github.com/IBM/couchbackup

## Required tools and credentials

- Node.js LTS 22 or 24 and npm.
- Install CouchBackup with npm install --global @cloudant/couchbackup.
- age for client-side authenticated encryption.
- AWS CLI v2 for IBM Cloud Object Storage S3-compatible API.
- A dedicated COS bucket in the approved backup region.
- A dedicated COS HMAC service credential restricted to that bucket.
- An age identity stored separately from IBM Cloud and GitHub. Backup jobs need only the public recipient; restore operators need the private identity.

Do not reuse the Code Engine runtime Cloudant Writer credential if a separate least-privilege backup identity can be provisioned. Never put credentials or the age private identity in GitHub.

## Backup

Provide these values through a protected job runner or secret manager: CLOUDANT_URL, CLOUDANT_API_KEY, CLOUDANT_DATABASE, AGE_RECIPIENT, COS_BUCKET, COS_ENDPOINT, AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.

Run: bash scripts/cloudant-backup.sh

The script streams CouchBackup output through gzip and age encryption. The plaintext stream is not written to disk. It calculates a SHA-256 checksum, uploads the encrypted object and checksum to COS, then removes its private temporary directory.

Schedule this in a protected runner once daily only after the bucket, credentials, encryption-key recovery and retention policy are approved. Alert on every failed run. A successful upload is not a restore test.

## Restore

Create a new, empty Cloudant database first. CouchBackup cannot restore into a database with old tombstones, even if all visible documents were deleted.

Provide the backup settings plus AGE_IDENTITY_FILE, BACKUP_OBJECT (object key relative to the bucket) and RESTORE_DATABASE (new database name, never the production database).

Run: bash scripts/cloudant-restore.sh

After restore:
1. Compare source and restored document counts.
2. Verify representative user-scoped document IDs without exposing financial values in logs.
3. Verify user isolation and authentication in an isolated recovery deployment.
4. Recreate database security settings and required indexes/configuration. CouchBackup does not restore security settings.
5. Record recovery time and the data-loss window.
6. Do not point production traffic at the restored database until cutover is approved.

Never restore over the production database.

## Retention and deletion

No automatic deletion policy is enabled. The data controller must approve retention periods for active financial records, audit events, backup copies and deleted-account data before destructive cleanup is scheduled. Configure COS lifecycle expiry only after that decision and any legal holds are documented.

Deletion from the live database does not erase records in older backup snapshots. Explain backup expiry in the privacy notice.

## Required IBM Cloud work

- [ ] Create the dedicated COS bucket in the approved backup region.
- [ ] Enable versioning if supported and define lifecycle expiry after retention approval.
- [ ] Create least-privilege HMAC credentials.
- [ ] Generate an age key pair and store the private identity separately.
- [ ] Configure a protected scheduled runner and secret injection.
- [ ] Run a first backup and verify encrypted object plus checksum exist.
- [ ] Restore into a new empty Cloudant database.
- [ ] Complete recovery validation and record evidence.
- [ ] Approve RPO (maximum acceptable data loss) and RTO (maximum acceptable recovery time).

Until the restore test succeeds, backups are not operationally verified and FINANCIAL_DATA_ENABLED must remain false.
