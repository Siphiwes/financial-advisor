# Operations checklist

## Current prototype

- Confirm Code Engine revision is Ready after deployment.
- Check application logs for startup errors. Never add secrets or financial document contents to logs.
- Smoke-test `/` and `/health` after each release.
- Review IBM Cloud usage and service quotas regularly, especially on free plans.

## Before real users or financial data

- Add authenticated access and enforce per-user authorization.
- Establish backup, restore and deletion procedures; test recovery rather than assuming backups work.
- Add structured logs, metrics, alerting and request correlation IDs without sensitive payloads.
- Set request size, rate and timeout limits.
- Define incident response, credential rotation and dependency patching processes.
- Review data retention, consent, privacy and applicable South African legal requirements.
