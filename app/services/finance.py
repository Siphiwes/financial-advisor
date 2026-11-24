"""Financial account, transaction, budget and goal services.

All persisted records are scoped to the authenticated user. Monetary values are
stored as decimal strings to avoid binary floating-point conversion.
"""

import hashlib
import json
import re
from calendar import monthrange
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.database.cloudant import get_cloudant_client, get_database_name
from app.database.scoped import (
    UserScopedDocumentNotFoundError,
    create_user_scoped_document,
    delete_user_scoped_document,
    get_user_scoped_document,
    list_user_scoped_documents,
    update_user_scoped_document,
)
from app.schemas.auth import AuthenticatedUser
from app.core.security import verify_password
from app.database.users import get_user_by_email
from app.schemas.finance import (
    CategorySummary,
    CurrencySummary,
    FinancialSummaryResponse,
    FNBImportCommitResponse,
)
from app.services.fnb_csv import FNBStatement


class FinanceRecordNotFoundError(LookupError):
    """Raised when a financial record is absent or belongs to another user."""


class FinanceValidationError(ValueError):
    """Raised when a financial operation violates a business rule."""


def _connection():
    return get_cloudant_client(), get_database_name()

def _now() -> str:
    return datetime.now(UTC).isoformat()

def _decimal_text(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None

def _record_view(document: dict) -> dict:
    return {
        **document.get("data", {}),
        "id": document["record_id"],
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
    }

def _read_record(user_id: str, collection: str, record_id: str) -> dict:
    client, database = _connection()
    try:
        document = get_user_scoped_document(
            client, database, user_id, collection, record_id
        )
    except ValueError as exc:
        raise FinanceRecordNotFoundError(
            "The requested record was not found."
        ) from exc
    if document is None:
        raise FinanceRecordNotFoundError("The requested record was not found.")
    return document

def _create_record(
    user_id: str,
    collection: str,
    data: dict,
    *,
    record_id: str | None = None,
) -> dict:
    client, database = _connection()
    saved_id = create_user_scoped_document(
        client,
        database,
        user_id,
        collection,
        data,
        record_id=record_id,
    )
    return _read_record(user_id, collection, saved_id)

def _update_record(user_id: str, collection: str, record_id: str, data: dict) -> dict:
    client, database = _connection()
    try:
        update_user_scoped_document(
            client, database, user_id, collection, record_id, data
        )
    except UserScopedDocumentNotFoundError as exc:
        raise FinanceRecordNotFoundError(
            "The requested record was not found."
        ) from exc
    return _read_record(user_id, collection, record_id)

def _list_records(
    user_id: str,
    collection: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], bool]:
    client, database = _connection()
    documents, has_more = list_user_scoped_documents(
        client,
        database,
        user_id,
        collection,
        limit=limit,
        offset=offset,
    )
    return [_record_view(document) for document in documents], has_more

def _list_all_records(user_id: str, collection: str) -> tuple[list[dict], bool]:
    return _list_records(
        user_id,
        collection,
        limit=10_000,
        offset=0,
    )

def get_financial_account(user_id: str, account_id: str, *, active: bool = True) -> dict:
    account = _record_view(_read_record(user_id, "accounts", account_id))
    if active and not account.get("is_active", True):
        raise FinanceRecordNotFoundError("The requested account is inactive.")
    return account

def create_financial_account(user: AuthenticatedUser, payload) -> dict:
    data = {
        "institution": payload.institution,
        "display_name": payload.display_name.strip(),
        "account_type": payload.account_type,
        "currency": payload.currency,
        "account_last_four": payload.account_last_four,
        "is_active": True,
    }
    return _record_view(_create_record(user.id, "accounts", data))

def list_financial_accounts(user: AuthenticatedUser) -> list[dict]:
    items, _ = _list_records(user.id, "accounts", limit=500)
    return [item for item in items if item.get("is_active", True)]

def update_financial_account(user: AuthenticatedUser, account_id: str, changes: dict) -> dict:
    document = _read_record(user.id, "accounts", account_id)
    data = dict(document["data"])
    data.update({key: value for key, value in changes.items() if value is not None})
    return _record_view(_update_record(user.id, "accounts", account_id, data))

def _validated_category(user: AuthenticatedUser, category: str | None) -> str | None:
    if category is None:
        return None
    for item in list_categories(user):
        if item["name"].casefold() == category.strip().casefold():
            return item["name"]
    raise FinanceValidationError("Select an existing category or create a new one.")


def create_manual_transaction(user: AuthenticatedUser, payload) -> dict:
    account = get_financial_account(user.id, payload.account_id)
    category = _validated_category(user, payload.category)
    transaction_date = payload.transaction_date.isoformat()
    amount = _decimal_text(payload.amount)
    service_fee = _decimal_text(payload.service_fee)
    balance_after = _decimal_text(payload.balance_after)
    data = {
        "account_id": payload.account_id,
        "transaction_date": transaction_date,
        "description": payload.description,
        "reference": payload.reference,
        "amount": amount,
        "currency": account["currency"],
        "service_fee": service_fee,
        "balance_after": balance_after,
        "category": category,
        "notes": payload.notes,
        "source": "manual",
        "import_id": None,
        "original": {
            "transaction_date": transaction_date,
            "description": payload.description,
            "reference": payload.reference,
            "amount": amount,
            "service_fee": service_fee,
            "balance_after": balance_after,
        },
        "corrections": [],
        "is_deleted": False,
    }
    return _record_view(_create_record(user.id, "transactions", data))

def get_transaction(user: AuthenticatedUser, transaction_id: str) -> dict:
    document = _read_record(user.id, "transactions", transaction_id)
    if document["data"].get("is_deleted"):
        raise FinanceRecordNotFoundError("The requested transaction was not found.")
    return _record_view(document)

def list_transactions(
    user: AuthenticatedUser,
    *,
    account_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], bool]:
    if from_date and to_date and from_date > to_date:
        raise FinanceValidationError("Start date cannot be after end date.")

    records, capped = _list_all_records(user.id, "transactions")
    filtered = []
    search_text = search.casefold().strip() if search else None
    for item in records:
        if item.get("is_deleted"):
            continue
        if account_id and item.get("account_id") != account_id:
            continue
        item_date = date.fromisoformat(item["transaction_date"])
        if from_date and item_date < from_date:
            continue
        if to_date and item_date > to_date:
            continue
        if category and item.get("category") != category:
            continue
        if search_text and search_text not in (
            f'{item.get("description", "")} {item.get("reference") or ""}'
        ).casefold():
            continue
        filtered.append(item)

    filtered.sort(
        key=lambda item: (
            item.get("transaction_date", ""),
            item.get("created_at", ""),
            item.get("id", ""),
        ),
        reverse=True,
    )
    return filtered[offset : offset + limit], capped or offset + limit < len(filtered)

def update_transaction(user: AuthenticatedUser, transaction_id: str, changes: dict) -> dict:
    document = _read_record(user.id, "transactions", transaction_id)
    data = dict(document["data"])
    if data.get("is_deleted"):
        raise FinanceRecordNotFoundError("The requested transaction was not found.")

    normalized = {}
    for key, value in changes.items():
        if value is None and key not in {"reference", "category", "notes"}:
            continue
        if key == "category" and value is not None:
            value = _validated_category(user, value)
        if key == "transaction_date":
            value = value.isoformat()
        elif key == "amount":
            value = _decimal_text(value)
        if data.get(key) != value:
            normalized[key] = value

    if not normalized:
        return _record_view(document)

    correction = {
        "changed_at": _now(),
        "changes": {
            key: {"from": data.get(key), "to": value}
            for key, value in normalized.items()
        },
    }
    data["corrections"] = (data.get("corrections") or [])[-49:] + [correction]
    data.update(normalized)
    return _record_view(_update_record(user.id, "transactions", transaction_id, data))

def delete_transaction(user: AuthenticatedUser, transaction_id: str) -> dict:
    document = _read_record(user.id, "transactions", transaction_id)
    data = dict(document["data"])
    if data.get("is_deleted"):
        raise FinanceRecordNotFoundError("The requested transaction was not found.")
    data["is_deleted"] = True
    data["deleted_at"] = _now()
    return _record_view(_update_record(user.id, "transactions", transaction_id, data))

def create_budget(user: AuthenticatedUser, payload) -> dict:
    category = _validated_category(user, payload.category)
    data = {
        "name": payload.name.strip(),
        "category": category,
        "amount": _decimal_text(payload.amount),
        "currency": payload.currency,
        "period": payload.period,
        "start_date": payload.start_date.isoformat(),
        "end_date": payload.end_date.isoformat() if payload.end_date else None,
        "is_active": True,
    }
    return _record_view(_create_record(user.id, "budgets", data))

def list_budgets(user: AuthenticatedUser) -> list[dict]:
    items, _ = _list_records(user.id, "budgets", limit=500)
    return [item for item in items if item.get("is_active", True)]

def update_budget(user: AuthenticatedUser, budget_id: str, changes: dict) -> dict:
    document = _read_record(user.id, "budgets", budget_id)
    data = dict(document["data"])
    for key, value in changes.items():
        if value is None:
            continue
        if key == "category":
            value = _validated_category(user, value)
        data[key] = value.isoformat() if isinstance(value, date) else (
            _decimal_text(value) if isinstance(value, Decimal) else value
        )
    return _record_view(_update_record(user.id, "budgets", budget_id, data))

def create_goal(user: AuthenticatedUser, payload) -> dict:
    data = {
        "name": payload.name.strip(),
        "description": payload.description,
        "target_amount": _decimal_text(payload.target_amount),
        "currency": payload.currency,
        "target_date": payload.target_date.isoformat() if payload.target_date else None,
        "saved_amount": "0.00",
        "contributions": [],
        "is_active": True,
    }
    return _record_view(_create_record(user.id, "goals", data))

def list_goals(user: AuthenticatedUser) -> list[dict]:
    items, _ = _list_records(user.id, "goals", limit=500)
    return [item for item in items if item.get("is_active", True)]

def update_goal(user: AuthenticatedUser, goal_id: str, changes: dict) -> dict:
    document = _read_record(user.id, "goals", goal_id)
    data = dict(document["data"])
    for key, value in changes.items():
        if value is None and key != "target_date":
            continue
        data[key] = value.isoformat() if isinstance(value, date) else (
            _decimal_text(value) if isinstance(value, Decimal) else value
        )
    return _record_view(_update_record(user.id, "goals", goal_id, data))

def financial_summary(
    user: AuthenticatedUser,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> FinancialSummaryResponse:
    if from_date and to_date and from_date > to_date:
        raise FinanceValidationError("Start date cannot be after end date.")

    records, capped = _list_all_records(user.id, "transactions")
    currency_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "income": Decimal("0"),
            "expenses": Decimal("0"),
            "transfers": Decimal("0"),
            "count": 0,
        }
    )
    category_totals: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"expenses": Decimal("0"), "count": 0}
    )
    category_kinds = {
        category_item["name"].casefold(): category_item["kind"]
        for category_item in list_categories(user)
    }

    for item in records:
        if item.get("is_deleted"):
            continue
        transaction_date = date.fromisoformat(item["transaction_date"])
        if from_date and transaction_date < from_date:
            continue
        if to_date and transaction_date > to_date:
            continue

        amount = Decimal(str(item["amount"]))
        currency = item["currency"]
        totals = currency_totals[currency]
        totals["count"] += 1
        category = item.get("category") or "Uncategorised"
        category_kind = category_kinds.get(
            category.casefold(),
            "income" if amount >= 0 else "expense",
        )
        if category_kind == "transfer":
            totals["transfers"] += abs(amount)
        elif amount >= 0:
            totals["income"] += amount
        else:
            totals["expenses"] += abs(amount)
            category_total = category_totals[(category, currency)]
            category_total["expenses"] += abs(amount)
            category_total["count"] += 1

    currencies = [
        CurrencySummary(
            currency=currency,
            income=values["income"],
            expenses=values["expenses"],
            net_cash_flow=values["income"] - values["expenses"],
            transfers=values["transfers"],
            transaction_count=values["count"],
        )
        for currency, values in sorted(currency_totals.items())
    ]
    expenses_by_category = [
        CategorySummary(
            category=category,
            currency=currency,
            expenses=values["expenses"],
            transaction_count=values["count"],
        )
        for (category, currency), values in sorted(category_totals.items())
    ]

    return FinancialSummaryResponse(
        from_date=from_date,
        to_date=to_date,
        currencies=currencies,
        expenses_by_category=expenses_by_category,
        data_limit_reached=capped,
    )

def _fnb_transaction_record_id(account_id: str, transaction) -> str:
    fingerprint = {
        "account_id": account_id,
        "transaction_date": transaction.effective_date.isoformat(),
        "description": transaction.description.strip(),
        "reference": transaction.reference or "",
        "amount": _decimal_text(transaction.amount),
        "service_fee": _decimal_text(transaction.service_fee),
        "balance_after": _decimal_text(transaction.balance),
    }
    canonical = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:32]

def commit_fnb_import(
    user: AuthenticatedUser,
    account_id: str,
    statement: FNBStatement,
    original_content: bytes,
) -> FNBImportCommitResponse:
    """Persist a confirmed FNB statement with retry-safe duplicate detection."""
    account = get_financial_account(user.id, account_id)
    if account.get("institution") != "FNB":
        raise FinanceValidationError("The selected account is not an FNB account.")
    if not account.get("account_last_four") or not statement.account_last_four:
        raise FinanceValidationError(
            "The FNB statement and selected account must both include the last four digits."
        )
    if account["account_last_four"] != statement.account_last_four:
        raise FinanceValidationError(
            "The account number on the statement does not match the selected account."
        )

    content_hash = hashlib.sha256(original_content).hexdigest()
    batch_id = hashlib.sha256(
        f"{user.id}|{account_id}|{content_hash}".encode()
    ).hexdigest()[:32]
    client, database = _connection()
    batch_document = get_user_scoped_document(
        client, database, user.id, "imports", batch_id
    )

    if batch_document and batch_document["data"].get("status") == "completed":
        stored = batch_document["data"]
        return FNBImportCommitResponse(
            import_id=batch_id,
            status="already_completed",
            transaction_count=stored["transaction_count"],
            imported_count=stored["imported_count"],
            duplicate_count=stored["duplicate_count"],
            statement_date=statement.statement_date,
            account_last_four=statement.account_last_four,
            message="This FNB statement has already been imported.",
        )

    if batch_document is None:
        batch_data = {
            "source": "FNB_CSV",
            "account_id": account_id,
            "file_sha256": content_hash,
            "status": "processing",
            "transaction_count": len(statement.transactions),
            "imported_count": 0,
            "duplicate_count": 0,
            "statement_date": (
                statement.statement_date.isoformat() if statement.statement_date else None
            ),
            "started_at": _now(),
            "completed_at": None,
        }
        try:
            create_user_scoped_document(
                client, database, user.id, "imports", batch_data, record_id=batch_id
            )
        except Exception as exc:
            if not _is_conflict_error(exc):
                raise
        batch_document = get_user_scoped_document(
            client, database, user.id, "imports", batch_id
        )
        if batch_document is None:
            raise RuntimeError("The FNB import batch could not be initialized.")

    imported_count = 0
    duplicate_count = 0
    transaction_occurrences: dict[str, int] = defaultdict(int)
    try:
        for transaction in statement.transactions:
            base_record_id = _fnb_transaction_record_id(account_id, transaction)
            occurrence = transaction_occurrences[base_record_id]
            transaction_occurrences[base_record_id] += 1
            record_id = (
                base_record_id
                if occurrence == 0
                else hashlib.sha256(
                    f"{base_record_id}:{occurrence}".encode()
                ).hexdigest()[:32]
            )
            existing = get_user_scoped_document(
                client, database, user.id, "transactions", record_id
            )
            if existing:
                if existing["data"].get("import_id") == batch_id:
                    imported_count += 1
                else:
                    duplicate_count += 1
                continue

            transaction_date = transaction.effective_date.isoformat()
            amount = _decimal_text(transaction.amount)
            service_fee = _decimal_text(transaction.service_fee)
            balance_after = _decimal_text(transaction.balance)
            transaction_data = {
                "account_id": account_id,
                "transaction_date": transaction_date,
                "description": transaction.description,
                "reference": transaction.reference,
                "amount": amount,
                "currency": account["currency"],
                "service_fee": service_fee,
                "balance_after": balance_after,
                "category": None,
                "notes": None,
                "source": "fnb_csv",
                "import_id": batch_id,
                "original": {
                    "transaction_date": transaction_date,
                    "description": transaction.description,
                    "reference": transaction.reference,
                    "amount": amount,
                    "service_fee": service_fee,
                    "balance_after": balance_after,
                },
                "corrections": [],
                "is_deleted": False,
            }
            try:
                create_user_scoped_document(
                    client,
                    database,
                    user.id,
                    "transactions",
                    transaction_data,
                    record_id=record_id,
                )
                imported_count += 1
            except Exception as exc:
                if not _is_conflict_error(exc):
                    raise
                duplicate_count += 1

        batch_data = dict(batch_document["data"])
        batch_data.update(
            {
                "status": "completed",
                "imported_count": imported_count,
                "duplicate_count": duplicate_count,
                "completed_at": _now(),
            }
        )
        update_user_scoped_document(
            client, database, user.id, "imports", batch_id, batch_data
        )
    except Exception:
        batch_data = dict(batch_document["data"])
        batch_data.update(
            {
                "status": "partial",
                "last_attempt_imported_count": imported_count,
                "last_attempt_duplicate_count": duplicate_count,
                "updated_at": _now(),
            }
        )
        try:
            update_user_scoped_document(
                client, database, user.id, "imports", batch_id, batch_data
            )
        except Exception:
            pass
        raise

    return FNBImportCommitResponse(
        import_id=batch_id,
        status="completed",
        transaction_count=len(statement.transactions),
        imported_count=imported_count,
        duplicate_count=duplicate_count,
        statement_date=statement.statement_date,
        account_last_four=statement.account_last_four,
        message="The FNB statement was imported. Original transaction values were preserved.",
    )

def _is_conflict_error(error: Exception) -> bool:
    return (
        getattr(error, "code", None) == 409
        or getattr(error, "status_code", None) == 409
    )

_SYSTEM_CATEGORIES = [
    {"name": "Salary", "kind": "income"},
    {"name": "Business income", "kind": "income"},
    {"name": "Interest", "kind": "income"},
    {"name": "Housing", "kind": "expense"},
    {"name": "Groceries", "kind": "expense"},
    {"name": "Transport", "kind": "expense"},
    {"name": "Utilities", "kind": "expense"},
    {"name": "Healthcare", "kind": "expense"},
    {"name": "Insurance", "kind": "expense"},
    {"name": "Debt repayments", "kind": "expense"},
    {"name": "Education", "kind": "expense"},
    {"name": "Entertainment", "kind": "expense"},
    {"name": "Shopping", "kind": "expense"},
    {"name": "Personal care", "kind": "expense"},
    {"name": "Subscriptions", "kind": "expense"},
    {"name": "Bank fees", "kind": "expense"},
    {"name": "Transfers", "kind": "transfer"},
    {"name": "Other", "kind": "expense"},
]

def list_categories(user: AuthenticatedUser) -> list[dict]:
    """Return built-in categories and the current user's custom categories."""
    custom, _ = _list_records(user.id, "categories", limit=500)
    custom = [item for item in custom if item.get("is_active", True)]
    system = [
        {
            "id": f"system-{index + 1}",
            **category,
            "is_system": True,
            "is_active": True,
            "created_at": None,
            "updated_at": None,
        }
        for index, category in enumerate(_SYSTEM_CATEGORIES)
    ]
    return system + custom

def create_category(user: AuthenticatedUser, name: str, kind: str) -> dict:
    """Create a user-owned category without changing the built-in catalogue."""
    normalized_name = name.strip()
    if any(
        item["name"].casefold() == normalized_name.casefold()
        for item in list_categories(user)
    ):
        raise FinanceValidationError("A category with this name already exists.")

    return _record_view(
        _create_record(
            user.id,
            "categories",
            {
                "name": normalized_name,
                "kind": kind,
                "is_system": False,
                "is_active": True,
            },
        )
    )

def update_category(user: AuthenticatedUser, category_id: str, changes: dict) -> dict:
    """Update or deactivate a user-owned category."""
    if category_id.startswith("system-"):
        raise FinanceValidationError("Built-in categories cannot be changed.")
    document = _read_record(user.id, "categories", category_id)
    data = dict(document["data"])
    if data.get("is_system"):
        raise FinanceValidationError("Built-in categories cannot be changed.")
    new_name = changes.get("name")
    if new_name and any(
        item["id"] != category_id
        and item["name"].casefold() == new_name.strip().casefold()
        for item in list_categories(user)
    ):
        raise FinanceValidationError("A category with this name already exists.")
    for key, value in changes.items():
        if value is not None:
            data[key] = value
    return _record_view(_update_record(user.id, "categories", category_id, data))

def list_import_records(user: AuthenticatedUser) -> list[dict]:
    """List import metadata only, never the uploaded bank statement itself."""
    items, _ = _list_records(user.id, "imports", limit=500)
    return items

def get_import_record(user: AuthenticatedUser, import_id: str) -> dict:
    return _record_view(_read_record(user.id, "imports", import_id))



def get_goal(user: AuthenticatedUser, goal_id: str) -> dict:
    """Read one goal owned by the authenticated user."""
    document = _read_record(user.id, "goals", goal_id)
    if not document["data"].get("is_active", True):
        raise FinanceRecordNotFoundError("The requested goal was not found.")
    return _record_view(document)


def add_goal_contribution(user: AuthenticatedUser, goal_id: str, payload) -> dict:
    """Record a user-entered contribution or withdrawal against a goal."""
    document = _read_record(user.id, "goals", goal_id)
    data = dict(document["data"])
    if not data.get("is_active", True):
        raise FinanceRecordNotFoundError("The requested goal was not found.")

    current_saved = Decimal(str(data.get("saved_amount", "0")))
    contribution = payload.amount
    if payload.direction == "withdrawal":
        if contribution > current_saved:
            raise FinanceValidationError(
                "A withdrawal cannot exceed the goal's recorded saved amount."
            )
        updated_saved = current_saved - contribution
    else:
        updated_saved = current_saved + contribution

    history = list(data.get("contributions") or [])
    if len(history) >= 1000:
        raise FinanceValidationError(
            "The contribution history reached its record limit."
        )

    history.append(
        {
            "amount": _decimal_text(contribution),
            "transaction_date": payload.transaction_date.isoformat(),
            "direction": payload.direction,
            "notes": payload.notes,
            "recorded_at": _now(),
        }
    )
    data["saved_amount"] = _decimal_text(updated_saved)
    data["contributions"] = history
    return _record_view(_update_record(user.id, "goals", goal_id, data))


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _budget_period_dates(budget: dict, today: date) -> tuple[date, date]:
    start = date.fromisoformat(budget["start_date"])
    period = budget["period"]
    if period == "weekly":
        elapsed_weeks = max(0, (today - start).days // 7)
        period_start = start + timedelta(weeks=elapsed_weeks)
        period_end = period_start + timedelta(days=6)
    else:
        months = {"monthly": 1, "quarterly": 3, "yearly": 12}[period]
        elapsed_months = max(0, (today.year - start.year) * 12 + today.month - start.month)
        period_offset = (elapsed_months // months) * months
        period_start = _add_months(start, period_offset)
        period_end = _add_months(period_start, months) - timedelta(days=1)

    configured_end = (
        date.fromisoformat(budget["end_date"]) if budget.get("end_date") else None
    )
    if configured_end and configured_end < period_end:
        period_end = configured_end
    if period_start < start:
        period_start = start
    return period_start, period_end


def list_budget_progress(user: AuthenticatedUser, *, today: date | None = None) -> list[dict]:
    """Calculate budget usage from the user's own saved transactions."""
    today = today or date.today()
    budgets = list_budgets(user)
    transactions, _ = _list_all_records(user.id, "transactions")
    progress = []

    for budget in budgets:
        period_start, period_end = _budget_period_dates(budget, today)
        spent = Decimal("0")
        if today >= period_start:
            for transaction in transactions:
                if transaction.get("is_deleted") or transaction.get("amount") is None:
                    continue
                transaction_date = date.fromisoformat(transaction["transaction_date"])
                if not period_start <= transaction_date <= min(period_end, today):
                    continue
                if transaction.get("category") != budget["category"]:
                    continue
                if transaction.get("currency") != budget["currency"]:
                    continue
                amount = Decimal(str(transaction["amount"]))
                if amount < 0:
                    spent += abs(amount)

        budget_amount = Decimal(str(budget["amount"]))
        progress.append(
            {
                **budget,
                "period_start": period_start,
                "period_end": period_end,
                "spent": spent,
                "remaining": budget_amount - spent,
                "percent_used": (
                    (spent / budget_amount * Decimal("100"))
                    if budget_amount > 0
                    else Decimal("0")
                ),
            }
        )

    return progress


def recurring_payment_candidates(user: AuthenticatedUser) -> list[dict]:
    """Identify possible recurring debits from the user's actual transaction records."""
    transactions, _ = _list_all_records(user.id, "transactions")
    category_kinds = {
        category_item["name"].casefold(): category_item["kind"]
        for category_item in list_categories(user)
    }
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for transaction in transactions:
        if transaction.get("is_deleted"):
            continue
        amount = Decimal(str(transaction["amount"]))
        category = (transaction.get("category") or "").casefold()
        if amount >= 0 or category_kinds.get(category) == "transfer":
            continue
        description = re.sub(
            r"\d+",
            "",
            transaction.get("description", "").casefold(),
        )
        normalized_description = " ".join(description.split())
        if not normalized_description:
            continue
        key = (
            transaction["account_id"],
            normalized_description,
            transaction["currency"],
        )
        grouped[key].append(transaction)

    candidates = []
    for (account_id, _normalized_description, currency), entries in grouped.items():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda item: item["transaction_date"])
        dates = [date.fromisoformat(item["transaction_date"]) for item in entries]
        gaps = [(dates[index] - dates[index - 1]).days for index in range(1, len(dates))]
        average_gap = sum(gaps) / len(gaps)
        if 5 <= average_gap <= 9:
            frequency = "weekly"
        elif 25 <= average_gap <= 35:
            frequency = "monthly"
        else:
            frequency = "irregular"

        amounts = [abs(Decimal(str(item["amount"]))) for item in entries]
        average_amount = sum(amounts, Decimal("0")) / len(amounts)
        candidates.append(
            {
                "account_id": account_id,
                "description": entries[-1]["description"],
                "average_amount": average_amount,
                "currency": currency,
                "occurrence_count": len(entries),
                "first_seen": dates[0],
                "last_seen": dates[-1],
                "frequency": frequency,
                "confidence": "medium" if len(entries) >= 3 and frequency != "irregular" else "low",
            }
        )

    candidates.sort(
        key=lambda item: (item["last_seen"], item["description"]),
        reverse=True,
    )
    return candidates[:100]



_PRIVACY_COLLECTIONS = (
    "accounts",
    "transactions",
    "categories",
    "budgets",
    "goals",
    "imports",
    "audit",
)


def export_user_data(user: AuthenticatedUser) -> dict:
    """Build a bounded export of the authenticated user's own application data."""
    exported: dict[str, list[dict]] = {}
    counts: dict[str, int] = {}
    for collection in _PRIVACY_COLLECTIONS:
        items, has_more = _list_records(
            user.id,
            collection,
            limit=10_000,
            offset=0,
        )
        if has_more:
            raise FinanceValidationError(
                "This account contains more than 10,000 records in one collection. "
                "Contact support for a complete paginated export."
            )
        exported[collection] = items
        counts[collection] = len(items)

    return {
        "exported_at": datetime.now(UTC),
        "user_id": user.id,
        "email": user.email,
        "data": exported,
        "record_counts": counts,
        "original_statement_files_included": False,
    }


def delete_user_data_and_account(user: AuthenticatedUser, current_password: str) -> dict:
    """Delete all user-owned finance documents and the Cloudant login document.

    The account document is deleted last. If a Cloudant operation fails, the
    account remains active so the user can authenticate and retry deletion.
    """
    client, database = _connection()
    user_document = get_user_by_email(client, database, user.email)
    if (
        not user_document
        or user_document.get("type") != "user"
        or user_document.get("user_id") != user.id
        or not user_document.get("_rev")
        or not user_document.get("password_hash")
        or not verify_password(current_password, user_document["password_hash"])
    ):
        raise FinanceValidationError(
            "The current password is incorrect or the account could not be verified."
        )

    documents_by_collection: dict[str, list[dict]] = {}

    # Check all collections for the supported deletion bound before removing
    # any records, avoiding a known partial delete when a collection is too large.
    for collection in _PRIVACY_COLLECTIONS:
        documents, has_more = list_user_scoped_documents(
            client,
            database,
            user.id,
            collection,
            limit=10_000,
            offset=0,
        )
        if has_more:
            raise FinanceValidationError(
                "This account contains more than 10,000 records in one collection. "
                "Contact support to complete a controlled deletion."
            )
        documents_by_collection[collection] = documents

    deleted_counts: dict[str, int] = {}
    for collection, documents in documents_by_collection.items():
        deleted_count = 0
        for document in documents:
            result = delete_user_scoped_document(
                client,
                database,
                user.id,
                collection,
                document["record_id"],
            )
            if result is not True:
                raise RuntimeError("Cloudant did not confirm a financial record deletion.")
            deleted_count += 1
        deleted_counts[collection] = deleted_count

    user_result = client.delete_document(
        db=database,
        doc_id=user_document["_id"],
        rev=user_document["_rev"],
    ).get_result()
    if user_result.get("ok") is not True:
        raise RuntimeError("Cloudant did not confirm account deletion.")

    return {
        "deleted": True,
        "deleted_record_counts": deleted_counts,
        "account_access_revoked": True,
        "message": "The financial records and login account were deleted.",
    }
