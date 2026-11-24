"""Idempotent persistence workflow for a user-confirmed FNB CSV import."""

import hashlib
import json
from collections import Counter
from decimal import Decimal

from app.database.scoped import (
    UserScopedDocumentConflictError,
    bulk_create_user_scoped_documents,
    create_user_scoped_document,
    get_user_scoped_document,
    list_user_scoped_documents,
    update_user_scoped_document,
)
from app.services.fnb_csv import FNBStatement, parse_fnb_csv

IMPORT_COLLECTION = "imports"
TRANSACTION_COLLECTION = "transactions"
MAX_IMPORT_ROWS = 10_000


class FNBImportAlreadyRunningError(RuntimeError):
    """Raised when another request is processing the same statement."""


def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _validate_money_precision(value: Decimal | None) -> None:
    if value is None:
        return
    if value.as_tuple().exponent < -2 or abs(value) >= Decimal("10000000000000000"):
        raise ValueError(
            "The FNB statement contains a monetary value that exceeds the supported "
            "precision of 16 whole digits and 2 decimal places."
        )


def _import_record_id(user_id: str, account_id: str, content_digest: str) -> str:
    source = f"{user_id}:{account_id}:{content_digest}".encode("utf-8")
    return hashlib.sha256(source).hexdigest()[:32]


def _transaction_record_id(
    account_id: str,
    transaction: dict,
    duplicate_occurrence: int,
) -> str:
    fingerprint = {
        "account_id": account_id,
        "transaction_date": transaction["transaction_date"],
        "description": transaction["description"],
        "reference": transaction["reference"],
        "amount": transaction["amount"],
        "currency": transaction["currency"],
        "service_fee": transaction["service_fee"],
        "balance": transaction["balance"],
        "occurrence": duplicate_occurrence,
    }
    encoded = json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:32]


def _read_imported_transaction_ids(
    client,
    database: str,
    user_id: str,
    import_id: str,
) -> set[str]:
    ids: set[str] = set()
    bookmark = None
    while True:
        result = list_user_scoped_documents(
            client,
            database,
            user_id,
            TRANSACTION_COLLECTION,
            limit=200,
            bookmark=bookmark,
            filters={"data.import_id": import_id},
        )
        ids.update(document["record_id"] for document in result["documents"])
        bookmark = result.get("bookmark")
        if not bookmark:
            break
    return ids


def confirm_fnb_csv_import(
    client,
    database: str,
    user_id: str,
    account_document: dict,
    content: bytes,
) -> dict:
    """Persist parsed transactions after an explicit user confirmation.

    The original upload is not retained. Deterministic IDs make retries safe,
    and a confirmed import is bound to one user and one financial account.
    """
    statement: FNBStatement = parse_fnb_csv(content)
    if not 1 <= len(statement.transactions) <= MAX_IMPORT_ROWS:
        raise ValueError("The FNB statement transaction count is outside the supported range.")
    if any(not transaction.description.strip() for transaction in statement.transactions):
        raise ValueError("An FNB transaction row has no description.")
    for transaction in statement.transactions:
        _validate_money_precision(transaction.amount)
        _validate_money_precision(transaction.service_fee)
        _validate_money_precision(transaction.balance)

    account_id = account_document["record_id"]
    account_data = account_document["data"]
    currency = account_data["currency"]
    if account_data.get("institution") != "FNB":
        raise ValueError("The selected account is not an FNB account.")
    if (
        statement.account_last_four
        and account_data.get("account_last_four")
        and statement.account_last_four != account_data["account_last_four"]
    ):
        raise ValueError("The statement account does not match the selected financial account.")
    content_digest = hashlib.sha256(content).hexdigest()
    import_id = _import_record_id(user_id, account_id, content_digest)

    batch = get_user_scoped_document(client, database, user_id, IMPORT_COLLECTION, import_id)
    if batch and batch["data"].get("status") == "completed":
        return {
            "import_id": import_id,
            "status": "completed",
            "transaction_count": batch["data"]["transaction_count"],
            "imported_count": batch["data"]["imported_count"],
            "duplicate_count": batch["data"]["duplicate_count"],
            "already_imported": True,
        }
    if batch and batch["data"].get("status") == "processing":
        raise FNBImportAlreadyRunningError("This statement import is already being processed.")

    batch_data = {
        "bank": "FNB",
        "source_format": "FNB CSV",
        "account_id": account_id,
        "source_sha256": content_digest,
        "file_size_bytes": len(content),
        "statement_date": statement.statement_date.isoformat()
        if statement.statement_date
        else None,
        "account_last_four": account_data.get("account_last_four") or statement.account_last_four,
        "transaction_count": len(statement.transactions),
        "imported_count": 0,
        "duplicate_count": 0,
        "status": "processing",
        "failure_code": None,
    }

    if batch is None:
        try:
            create_user_scoped_document(
                client,
                database,
                user_id,
                IMPORT_COLLECTION,
                batch_data,
                record_id=import_id,
            )
        except UserScopedDocumentConflictError:
            existing = get_user_scoped_document(
                client, database, user_id, IMPORT_COLLECTION, import_id
            )
            if existing and existing["data"].get("status") == "completed":
                return {
                    "import_id": import_id,
                    "status": "completed",
                    "transaction_count": existing["data"]["transaction_count"],
                    "imported_count": existing["data"]["imported_count"],
                    "duplicate_count": existing["data"]["duplicate_count"],
                    "already_imported": True,
                }
            raise FNBImportAlreadyRunningError(
                "This statement import is already being processed."
            )
    else:
        update_user_scoped_document(
            client,
            database,
            user_id,
            IMPORT_COLLECTION,
            import_id,
            {**batch["data"], **batch_data},
        )

    occurrence_counts: Counter[str] = Counter()
    records: list[tuple[str, dict]] = []
    for transaction in statement.transactions:
        data = {
            "account_id": account_id,
            "import_id": import_id,
            "transaction_date": transaction.effective_date.isoformat(),
            "description": transaction.description,
            "reference": transaction.reference,
            "amount": _decimal_text(transaction.amount),
            "currency": currency,
            "service_fee": _decimal_text(transaction.service_fee),
            "balance": _decimal_text(transaction.balance),
            "category_id": None,
            "merchant_override": None,
            "notes": None,
            "source": "fnb_csv",
            "is_reviewed": False,
            "is_deleted": False,
        }
        base_key = json.dumps(
            {
                "account_id": account_id,
                "transaction_date": data["transaction_date"],
                "description": data["description"],
                "reference": data["reference"],
                "amount": data["amount"],
                "currency": data["currency"],
                "service_fee": data["service_fee"],
                "balance": data["balance"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        occurrence_counts[base_key] += 1
        record_id = _transaction_record_id(
            account_id,
            data,
            occurrence_counts[base_key],
        )
        records.append((record_id, data))

    try:
        already_saved_ids = _read_imported_transaction_ids(
            client, database, user_id, import_id
        )
        records_to_write = [
            (record_id, data)
            for record_id, data in records
            if record_id not in already_saved_ids
        ]
        bulk_result = bulk_create_user_scoped_documents(
            client,
            database,
            user_id,
            TRANSACTION_COLLECTION,
            records_to_write,
        )
        imported_count = len(already_saved_ids) + bulk_result["created"]
        duplicate_count = len(records) - imported_count

        completed_data = {
            **batch_data,
            "status": "completed",
            "imported_count": imported_count,
            "duplicate_count": duplicate_count,
            "failure_code": None,
        }
        update_user_scoped_document(
            client,
            database,
            user_id,
            IMPORT_COLLECTION,
            import_id,
            completed_data,
        )
    except Exception:
        try:
            failed_batch = get_user_scoped_document(
                client, database, user_id, IMPORT_COLLECTION, import_id
            )
            if failed_batch:
                update_user_scoped_document(
                    client,
                    database,
                    user_id,
                    IMPORT_COLLECTION,
                    import_id,
                    {
                        **failed_batch["data"],
                        "status": "failed",
                        "failure_code": "import_write_failed",
                    },
                )
        except Exception:
            pass
        raise

    return {
        "import_id": import_id,
        "status": "completed",
        "transaction_count": len(records),
        "imported_count": imported_count,
        "duplicate_count": duplicate_count,
        "already_imported": False,
    }
