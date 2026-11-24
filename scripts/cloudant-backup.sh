#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
for name in CLOUDANT_URL CLOUDANT_API_KEY CLOUDANT_DATABASE AGE_RECIPIENT COS_BUCKET COS_ENDPOINT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION; do
  if [[ -z "$(printenv "$name" || true)" ]]; then
    printf 'Required environment variable is missing: %s\n' "$name" >&2
    exit 2
  fi
done
for command_name in couchbackup age aws gzip sha256sum; do
  command -v "$command_name" >/dev/null 2>&1 || { printf 'Required command is not installed: %s\n' "$command_name" >&2; exit 2; }
done
if [[ ! "$CLOUDANT_DATABASE" =~ ^[a-z][a-z0-9_$()+-]*$ ]]; then
  printf 'CLOUDANT_DATABASE contains unsupported characters.\n' >&2
  exit 2
fi
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
work_dir="$(mktemp -d)"
chmod 700 "$work_dir"
cleanup() { rm -rf "$work_dir"; }
trap cleanup EXIT INT TERM
backup_name="$(printf '%s-%s.jsonl.gz.age' "$CLOUDANT_DATABASE" "$timestamp")"
backup_path="$work_dir/$backup_name"
checksum_path="$work_dir/$backup_name.sha256"
printf 'Starting Cloudant backup for database %s at %s\n' "$CLOUDANT_DATABASE" "$timestamp" >&2
couchbackup --url "$CLOUDANT_URL" --db "$CLOUDANT_DATABASE" --iam-api-key "$CLOUDANT_API_KEY" --quiet \
  | gzip -9 \
  | age --recipient "$AGE_RECIPIENT" --output "$backup_path"
test -s "$backup_path"
(cd "$work_dir" && sha256sum "$backup_name" > "$backup_name.sha256")
aws --endpoint-url "$COS_ENDPOINT" s3 cp "$backup_path" "s3://$COS_BUCKET/cloudant/$backup_name" --only-show-errors
aws --endpoint-url "$COS_ENDPOINT" s3 cp "$checksum_path" "s3://$COS_BUCKET/cloudant/$backup_name.sha256" --only-show-errors
printf 'Encrypted backup uploaded: s3://%s/cloudant/%s\n' "$COS_BUCKET" "$backup_name" >&2
