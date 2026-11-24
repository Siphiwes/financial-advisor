# Data retention policy decision record

**Status: approval required. No automated retention deletion is enabled.**

The data controller must approve retention periods before real financial data is processed. Do not infer a retention period from a technical default.

| Data class | Purpose | Retention period | Deletion trigger | Backup expiry |
|---|---|---|---|---|
| Account profile and authentication metadata | Account operation and security | Owner decision required | Verified account deletion or lawful request | Owner decision required |
| Imported transaction records | User-requested financial analysis | Owner decision required | User deletion request or defined account closure policy | Owner decision required |
| Import metadata and file hashes | Duplicate prevention and import history | Owner decision required | Linked account/data deletion or approved schedule | Owner decision required |
| Security and privacy audit events | Security investigation and accountability | Owner decision required | Approved audit schedule | Owner decision required |
| Encrypted Cloudant backups | Disaster recovery | Owner decision required | COS lifecycle expiry after approval | Owner decision required |
| Verification and password-reset tokens | Account lifecycle security | Short-lived, single-use; exact expiry to be configured | Successful use or expiry | Exclude expired tokens where practical |

## Mandatory controls

- Explain retention and backup expiry in the privacy notice before collection.
- Deletion from live Cloudant does not erase documents in older backup snapshots.
- Restrict backup access to the recovery role and encrypt backups client-side.
- Audit backup and restore administration without logging secrets or financial content.
- Apply approved COS lifecycle rules and test object expiry.
- Document legal holds and how expiry is suspended.
- Review the policy annually and whenever processing purposes or providers change.

Approver:
Approval date:
Policy version:
Next review date:
