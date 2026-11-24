# Operations checklist

## Release deployment

- Confirm the Code Engine revision is Ready.
- Confirm / and /health respond.
- Confirm the browser UI loads its CSS and JavaScript.
- Confirm login and /auth/me work.
- Check logs for startup errors without logging secrets or financial payloads.
- Confirm Cloudant queries and index creation are allowed by the service credential.
- Confirm Cloudant diagnostics remain disabled.

## FNB import verification

- Use a CSV downloaded directly from the account holder's FNB Online Banking account.
- Confirm the selected account belongs to the signed-in user.
- Compare statement date, transaction count, date, description, reference, debit/credit sign, fee and balance against the original export.
- Confirm preview does not save transaction records.
- Confirm import requires an explicit user action.
- Confirm the original file is not retained.
- Retry the same file for the same account and verify the same completed import is returned.
- Validate overlapping statement imports and inspect duplicate counts.
- Do not treat an import as reconciled until its source values have been checked against FNB.

## Cloudant operations

- Ensure the service identity has the permissions required for document reads/writes, bulk writes and JSON index creation.
- Monitor database size, document count and index use.
- Configure scheduled backups and complete a restore test before relying on the service for important financial records.
- Document restore point objectives and recovery procedures.

## Security and privacy

- Keep JWT_SECRET_KEY and AUTH_EMAIL_INDEX_KEY separate and sufficiently random.
- Keep registration invitation codes private.
- Keep AI disabled until the data-processing review is approved.
- Define a retention schedule, user export and complete account deletion procedure.
- Establish audit logging for sensitive access and changes.
- Define incident response and credential rotation.
- Review cross-border processing and applicable South African privacy requirements.

## Cost monitoring

Monitor Code Engine, Cloudant storage/index usage, network traffic and any optional watsonx.ai inference costs. Add request and user-level AI rate limits before enabling the advisor for broader use.
