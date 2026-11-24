#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
for name in CLOUDANT_URL CLOUDANT_API_KEY AGE_IDENTITY_FILE COS_BUCKET COS_ENDPOINT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY BACKUP_OBJECT RESTORE_DATABASE; do
  if [[ -z "$(printenv "$name" || true)" ]]; then
    printf 'Required environment variable is missing: %s\n' "$name" >&2
    exit 2
  fi
done
for command_name in couchrestore age aws gzip sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || { printf 'Required command is not installed: %s\n' "$command_name" >&2; exit 2; }
done
[[ -f "$AGE_IDENTITY_FILE" ]] || { printf 'AGE_IDENTITY_FILE is not readable.\n' >&2; exit 2; }
[[ "$RESTORE_DATABASE" =~ ^[a-z][a-z0-9_$()+/-]*$ ]] || { printf 'Invalid restore database name.\n' >&2; exit 2; }
if [[ "$RESTORE_DATABASE" == "finance-advisor-db" ]]; then
  printf 'Restore target must not be the production database.\n' >&2
  exit 2
fi
work_dir="$(mktemp -d)"
chmod 700 "$work_dir"
cleanup() { rm -rf "$work_dir"; }
trap cleanup EXIT INT TERM
backup_name="$(basename "$BACKUP_OBJECT")"
encrypted_path="$work_dir/$backup_name"
checksum_path="$work_dir/$backup_name.sha256"
aws --endpoint-url "$COS_ENDPOINT" s3 cp "s3://$COS_BUCKET/$BACKUP_OBJECT" "$encrypted_path" --only-show-errors
aws --endpoint-url "$COS_ENDPOINT" s3 cp "s3://$COS_BUCKET/$BACKUP_OBJECT.sha256" "$checksum_path" --only-show-errors
(cd "$work_dir" && sha256sum --check "$backup_name.sha256")
printf 'Restoring into %s. The target must already exist and be empty.\n' "$RESTORE_DATABASE" >&2
age --decrypt --identity "$AGE_IDENTITY_FILE" "$encrypted_path" \
  | gzip -d \
  | couchrestore --url "$CLOUDANT_URL" --db "$RESTORE_DATABASE" --iam-api-key "$CLOUDANT_API_KEY" --quiet
printf 'Restore command completed. Verify document counts, user isolation and configuration before cutover.\n' >&2
