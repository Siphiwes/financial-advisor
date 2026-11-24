"""Authenticated financial account, transaction, budget and goal APIs."""

import hashlib
import logging
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.database.cloudant import (
    CloudantConfigurationError,
    get_cloudant_client,
    get_database_name,
)
from app.database.scoped import (
    UserScopedDocumentConflictError,
    create_user_scoped_document,
    get_user_scoped_document,
    list_user_scoped_documents,
    update_user_scoped_document,
)
from app.schemas.auth import AuthenticatedUser
from app.schemas.finance import (
    Budget,
    BudgetCreate,
    BudgetUpdate,
    Category,
    CategoryCreate,
    CategoryUpdate,
    FinancialAccount,
    FinancialAccountCreate,
    FinancialAccountUpdate,
    FinancialGoal,
    FinancialSummary,
    GoalContribution,
    GoalContributionCreate,
    GoalCreate,
    GoalUpdate,
    Transaction,
    TransactionCreate,
    TransactionUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["personal finance"])


def _connection():
    try:
        return get_cloudant_client(), get_database_name()
    except CloudantConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Cloudant is not configured.") from exc


def _handle_storage_error(exc: Exception) -> HTTPException:
    logger.warning("Financial data operation failed: %s", type(exc).__name__)
    return HTTPException(
        status_code=502,
        detail="The financial data operation could not be completed.",
    )


def _as_record(document: dict, model):
    payload = {
        "id": document["record_id"],
        **document["data"],
        "created_at": document["created_at"],
        "updated_at": document["updated_at"],
    }
    return model.model_validate(payload)


def _require_document(client, database: str, user_id: str, collection: str, record_id: str):
    document = get_user_scoped_document(client, database, user_id, collection, record_id)
    if document is None:
        raise HTTPException(status_code=404, detail="The requested record was not found.")
    return document


def _validate_account(client, database: str, user_id: str, account_id: str) -> dict:
    account = _require_document(client, database, user_id, "accounts", account_id)
    if account["data"].get("is_active") is not True:
        raise HTTPException(status_code=409, detail="The financial account is inactive.")
    return account


def _validate_category(
    client,
    database: str,
    user_id: str,
    category_id: str | None,
) -> dict | None:
    if category_id is None:
        return None
    category = _require_document(client, database, user_id, "categories", category_id)
    if category["data"].get("is_active") is not True:
        raise HTTPException(status_code=409, detail="The selected category is inactive.")
    return category


def _list_records(
    client,
    database: str,
    user_id: str,
    collection: str,
    limit: int,
    bookmark: str | None,
    filters: dict | None = None,
) -> dict:
    try:
        result = list_user_scoped_documents(
            client,
            database,
            user_id,
            collection,
            limit=limit,
            bookmark=bookmark,
            filters=filters,
        )
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return {
        "items": result["documents"],
        "next_bookmark": result.get("bookmark"),
    }


@router.post(
    "/accounts",
    response_model=FinancialAccount,
    status_code=status.HTTP_201_CREATED,
    summary="Add a financial account",
)
def create_account(
    payload: FinancialAccountCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    data = payload.model_dump(mode="json")
    data["is_active"] = True

    if data.get("account_last_four"):
        existing = _list_records(
            client,
            database,
            current_user.id,
            "accounts",
            100,
            None,
            {
                "data.institution": data["institution"],
                "data.account_last_four": data["account_last_four"],
            },
        )
        if existing["items"]:
            raise HTTPException(
                status_code=409,
                detail="An account with this institution and last four digits already exists.",
            )

    try:
        record_id = create_user_scoped_document(
            client, database, current_user.id, "accounts", data
        )
        document = _require_document(
            client, database, current_user.id, "accounts", record_id
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return _as_record(document, FinancialAccount)


@router.get("/accounts", response_model=dict, summary="List your financial accounts")
def list_accounts(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    bookmark: str | None = None,
):
    client, database = _connection()
    page = _list_records(
        client, database, current_user.id, "accounts", limit, bookmark
    )
    return {
        "items": [_as_record(item, FinancialAccount) for item in page["items"]],
        "next_bookmark": page["next_bookmark"],
    }


@router.get("/accounts/{account_id}", response_model=FinancialAccount)
def read_account(
    account_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    return _as_record(
        _require_document(client, database, current_user.id, "accounts", account_id),
        FinancialAccount,
    )


@router.patch("/accounts/{account_id}", response_model=FinancialAccount)
def update_account(
    account_id: str,
    payload: FinancialAccountUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(client, database, current_user.id, "accounts", account_id)
    data = {**document["data"], **payload.model_dump(exclude_unset=True, mode="json")}
    try:
        update_user_scoped_document(
            client, database, current_user.id, "accounts", account_id, data
        )
        updated = _require_document(
            client, database, current_user.id, "accounts", account_id
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise _handle_storage_error(exc) from exc
    return _as_record(updated, FinancialAccount)


@router.post(
    "/transactions",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manually recorded transaction",
)
def create_transaction(
    payload: TransactionCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    account = _validate_account(client, database, current_user.id, payload.account_id)
    category = _validate_category(client, database, current_user.id, payload.category_id)

    if payload.currency != account["data"]["currency"]:
        raise HTTPException(
            status_code=422,
            detail="The transaction currency must match the selected account currency.",
        )

    now = datetime.now(UTC).isoformat()
    data = {
        **payload.model_dump(mode="json"),
        "source": "manual",
        "import_id": None,
        "merchant_override": None,
        "is_reviewed": False,
        "category_id": category["record_id"] if category else None,
        "created_at": now,
        "updated_at": now,
        "is_deleted": False,
    }
    try:
        record_id = create_user_scoped_document(
            client, database, current_user.id, "transactions", data
        )
        document = _require_document(
            client, database, current_user.id, "transactions", record_id
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return _as_record(document, Transaction)


@router.get("/transactions", response_model=dict, summary="Search your transactions")
def list_transactions(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    account_id: str | None = None,
    category_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    bookmark: str | None = None,
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date.")

    filters: dict = {"data.is_deleted": {"$ne": True}}
    if account_id:
        filters["data.account_id"] = account_id
    if category_id:
        filters["data.category_id"] = category_id
    if from_date and to_date:
        filters["data.transaction_date"] = {
            "$gte": from_date.isoformat(),
            "$lte": to_date.isoformat(),
        }
    elif from_date:
        filters["data.transaction_date"] = {"$gte": from_date.isoformat()}
    elif to_date:
        filters["data.transaction_date"] = {"$lte": to_date.isoformat()}

    client, database = _connection()
    page = _list_records(
        client, database, current_user.id, "transactions", limit, bookmark, filters
    )
    visible = [
        _as_record(item, Transaction)
        for item in page["items"]
        if item["data"].get("is_deleted") is not True
    ]
    visible.sort(key=lambda item: (item.transaction_date, item.id), reverse=True)
    return {"items": visible, "next_bookmark": page["next_bookmark"]}


@router.get("/transactions/{transaction_id}", response_model=Transaction)
def read_transaction(
    transaction_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(
        client, database, current_user.id, "transactions", transaction_id
    )
    if document["data"].get("is_deleted") is True:
        raise HTTPException(status_code=404, detail="The requested record was not found.")
    return _as_record(document, Transaction)


@router.patch("/transactions/{transaction_id}", response_model=Transaction)
def update_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(
        client, database, current_user.id, "transactions", transaction_id
    )
    if document["data"].get("is_deleted") is True:
        raise HTTPException(status_code=404, detail="The requested record was not found.")

    changes = payload.model_dump(exclude_unset=True, mode="json")
    if "category_id" in changes:
        category = _validate_category(
            client, database, current_user.id, changes["category_id"]
        )
        changes["category_id"] = category["record_id"] if category else None

    data = {**document["data"], **changes, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        update_user_scoped_document(
            client, database, current_user.id, "transactions", transaction_id, data
        )
        updated = _require_document(
            client, database, current_user.id, "transactions", transaction_id
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise _handle_storage_error(exc) from exc
    return _as_record(updated, Transaction)


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(
        client, database, current_user.id, "transactions", transaction_id
    )
    if document["data"].get("is_deleted") is True:
        raise HTTPException(status_code=404, detail="The requested record was not found.")
    data = {
        **document["data"],
        "is_deleted": True,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        update_user_scoped_document(
            client, database, current_user.id, "transactions", transaction_id, data
        )
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return None


@router.post(
    "/categories",
    response_model=Category,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CategoryCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    data = {**payload.model_dump(mode="json"), "is_active": True}
    try:
        record_id = create_user_scoped_document(
            client, database, current_user.id, "categories", data
        )
        document = _require_document(
            client, database, current_user.id, "categories", record_id
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return _as_record(document, Category)


@router.get("/categories", response_model=dict)
def list_categories(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    bookmark: str | None = None,
):
    client, database = _connection()
    page = _list_records(
        client, database, current_user.id, "categories", limit, bookmark
    )
    return {
        "items": [_as_record(item, Category) for item in page["items"]],
        "next_bookmark": page["next_bookmark"],
    }


@router.patch("/categories/{category_id}", response_model=Category)
def update_category(
    category_id: str,
    payload: CategoryUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(client, database, current_user.id, "categories", category_id)
    data = {
        **document["data"],
        **payload.model_dump(exclude_unset=True, mode="json"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        update_user_scoped_document(
            client, database, current_user.id, "categories", category_id, data
        )
        updated = _require_document(
            client, database, current_user.id, "categories", category_id
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise _handle_storage_error(exc) from exc
    return _as_record(updated, Category)


@router.post(
    "/budgets",
    response_model=Budget,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    payload: BudgetCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    category = _validate_category(client, database, current_user.id, payload.category_id)
    data = {
        **payload.model_dump(mode="json"),
        "category_id": category["record_id"] if category else None,
        "is_active": True,
    }
    try:
        record_id = create_user_scoped_document(
            client, database, current_user.id, "budgets", data
        )
        document = _require_document(client, database, current_user.id, "budgets", record_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return _as_record(document, Budget)


@router.get("/budgets", response_model=dict)
def list_budgets(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    period: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    bookmark: str | None = None,
):
    filters = {"data.period": period} if period else None
    client, database = _connection()
    page = _list_records(
        client, database, current_user.id, "budgets", limit, bookmark, filters
    )
    return {
        "items": [_as_record(item, Budget) for item in page["items"]],
        "next_bookmark": page["next_bookmark"],
    }


@router.patch("/budgets/{budget_id}", response_model=Budget)
def update_budget(
    budget_id: str,
    payload: BudgetUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(client, database, current_user.id, "budgets", budget_id)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if "category_id" in changes:
        category = _validate_category(
            client, database, current_user.id, changes["category_id"]
        )
        changes["category_id"] = category["record_id"] if category else None
    data = {
        **document["data"],
        **changes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        update_user_scoped_document(
            client, database, current_user.id, "budgets", budget_id, data
        )
        updated = _require_document(client, database, current_user.id, "budgets", budget_id)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise _handle_storage_error(exc) from exc
    return _as_record(updated, Budget)


@router.get("/budgets/progress", response_model=list[dict])
def budget_progress(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    period: Annotated[str, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")],
):
    from calendar import monthrange

    year, month = (int(part) for part in period.split("-"))
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])
    client, database = _connection()

    budget_page = _list_records(
        client, database, current_user.id, "budgets", 200, None, {"data.period": period}
    )
    budgets = [
        item for item in budget_page["items"] if item["data"].get("is_active") is True
    ]

    transactions: list[dict] = []
    bookmark = None
    while True:
        page = _list_records(
            client,
            database,
            current_user.id,
            "transactions",
            500,
            bookmark,
            {
                "data.transaction_date": {
                    "$gte": first_day.isoformat(),
                    "$lte": last_day.isoformat(),
                },
                "data.is_deleted": {"$ne": True},
            },
        )
        transactions.extend(page["items"])
        bookmark = page.get("next_bookmark")
        if not bookmark:
            break
        if len(transactions) >= 10_000:
            raise HTTPException(
                status_code=413,
                detail="The selected month contains too many transactions for budget progress.",
            )

    category_kinds: dict[str, str] = {}
    bookmark = None
    while True:
        page = _list_records(
            client, database, current_user.id, "categories", 200, bookmark
        )
        category_kinds.update(
            {
                item["record_id"]: item["data"].get("kind")
                for item in page["items"]
            }
        )
        bookmark = page.get("next_bookmark")
        if not bookmark:
            break

    results = []
    for budget_document in budgets:
        budget = budget_document["data"]
        category_id = budget.get("category_id")
        spent = Decimal("0.00")
        for transaction_document in transactions:
            transaction = transaction_document["data"]
            if transaction.get("is_deleted") is True:
                continue
            if transaction.get("currency") != budget["currency"]:
                continue
            transaction_category = transaction.get("category_id")
            category_kind = category_kinds.get(transaction_category)
            if category_kind in {"income", "transfer"}:
                continue
            if category_id is not None and transaction_category != category_id:
                continue
            amount = Decimal(str(transaction["amount"]))
            if amount < 0:
                spent += abs(amount)

        budget_amount = Decimal(str(budget["amount"]))
        results.append(
            {
                "id": budget_document["record_id"],
                "name": budget["name"],
                "period": budget["period"],
                "currency": budget["currency"],
                "amount": budget_amount,
                "spent": spent,
                "remaining": budget_amount - spent,
                "is_over_budget": spent > budget_amount,
                "category_id": category_id,
            }
        )
    return results


@router.post(
    "/goals",
    response_model=FinancialGoal,
    status_code=status.HTTP_201_CREATED,
)
def create_goal(
    payload: GoalCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    data = {
        **payload.model_dump(mode="json"),
        "contributed_amount": "0.00",
        "is_active": True,
    }
    try:
        record_id = create_user_scoped_document(
            client, database, current_user.id, "goals", data
        )
        document = _require_document(client, database, current_user.id, "goals", record_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise _handle_storage_error(exc) from exc
    return _as_record(document, FinancialGoal)


def _goal_contributed_amount(
    client,
    database: str,
    user_id: str,
    goal_id: str,
) -> Decimal:
    total = Decimal("0.00")
    bookmark = None
    while True:
        page = list_user_scoped_documents(
            client,
            database,
            user_id,
            "goal_contributions",
            limit=200,
            bookmark=bookmark,
            filters={"data.goal_id": goal_id},
        )
        for contribution in page["documents"]:
            total += Decimal(str(contribution["data"]["amount"]))
        bookmark = page.get("bookmark")
        if not bookmark:
            return total


def _goal_response(client, database: str, user_id: str, document: dict) -> FinancialGoal:
    goal = _as_record(document, FinancialGoal)
    total = _goal_contributed_amount(client, database, user_id, document["record_id"])
    return goal.model_copy(update={"contributed_amount": total})


@router.get("/goals", response_model=dict)
def list_goals(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    bookmark: str | None = None,
):
    client, database = _connection()
    page = _list_records(client, database, current_user.id, "goals", limit, bookmark)
    return {
        "items": [
            _goal_response(client, database, current_user.id, item)
            for item in page["items"]
        ],
        "next_bookmark": page["next_bookmark"],
    }


@router.get("/goals/{goal_id}", response_model=FinancialGoal)
def read_goal(
    goal_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(client, database, current_user.id, "goals", goal_id)
    return _goal_response(client, database, current_user.id, document)


@router.post(
    "/goals/{goal_id}/contributions",
    response_model=GoalContribution,
    summary="Record a contribution toward a financial goal",
)
def add_goal_contribution(
    goal_id: str,
    payload: GoalContributionCreate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
):
    if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key must be 8 to 128 safe characters.",
        )

    client, database = _connection()
    goal = _require_document(client, database, current_user.id, "goals", goal_id)
    if goal["data"].get("is_active") is not True:
        raise HTTPException(status_code=409, detail="The financial goal is inactive.")

    record_id = hashlib.sha256(
        f"{goal_id}:{idempotency_key}".encode()
    ).hexdigest()[:32]
    existing = get_user_scoped_document(
        client, database, current_user.id, "goal_contributions", record_id
    )
    data = {
        "goal_id": goal_id,
        "amount": format(payload.amount, "f"),
        "currency": goal["data"]["currency"],
        "contribution_date": payload.contribution_date.isoformat(),
        "note": payload.note,
    }
    if existing is not None:
        existing_data = existing["data"]
        same_request = (
            Decimal(str(existing_data["amount"])) == payload.amount
            and existing_data["contribution_date"] == data["contribution_date"]
            and existing_data.get("note") == payload.note
        )
        if not same_request:
            raise HTTPException(
                status_code=409,
                detail="This idempotency key was already used for a different contribution.",
            )
    else:
        try:
            create_user_scoped_document(
                client,
                database,
                current_user.id,
                "goal_contributions",
                data,
                record_id=record_id,
            )
        except UserScopedDocumentConflictError:
            existing = _require_document(
                client,
                database,
                current_user.id,
                "goal_contributions",
                record_id,
            )
            if (
                Decimal(str(existing["data"]["amount"])) != payload.amount
                or existing["data"]["contribution_date"] != data["contribution_date"]
                or existing["data"].get("note") != payload.note
            ):
                raise HTTPException(
                    status_code=409,
                    detail="This idempotency key was already used for a different contribution.",
                ) from None
        except Exception as exc:
            raise _handle_storage_error(exc) from exc
        else:
            existing = _require_document(
                client,
                database,
                current_user.id,
                "goal_contributions",
                record_id,
            )
    return _as_record(existing, GoalContribution)


@router.patch("/goals/{goal_id}", response_model=FinancialGoal)
def update_goal(
    goal_id: str,
    payload: GoalUpdate,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
):
    client, database = _connection()
    document = _require_document(client, database, current_user.id, "goals", goal_id)
    changes = payload.model_dump(exclude_unset=True, mode="json")
    data = {
        **document["data"],
        **changes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        update_user_scoped_document(client, database, current_user.id, "goals", goal_id, data)
        updated = _require_document(client, database, current_user.id, "goals", goal_id)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise _handle_storage_error(exc) from exc
    return _goal_response(client, database, current_user.id, updated)


@router.get("/analytics/summary", response_model=FinancialSummary)
def financial_summary(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    from_date: date,
    to_date: date,
    currency: str = "ZAR",
):
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date.")
    if len(currency) != 3 or not currency.isalpha() or currency.upper() != currency:
        raise HTTPException(
            status_code=422,
            detail="currency must be a three-letter uppercase code.",
        )

    client, database = _connection()
    transactions: list[dict] = []
    bookmark = None
    try:
        while True:
            page = list_user_scoped_documents(
                client,
                database,
                current_user.id,
                "transactions",
                limit=200,
                bookmark=bookmark,
                filters={
                    "data.transaction_date": {
                        "$gte": from_date.isoformat(),
                        "$lte": to_date.isoformat(),
                    },
                    "data.is_deleted": {"$ne": True},
                },
            )
            transactions.extend(page["documents"])
            bookmark = page.get("bookmark")
            if not bookmark or len(transactions) >= 10_000:
                break
    except Exception as exc:
        raise _handle_storage_error(exc) from exc

    if len(transactions) >= 10_000 and bookmark:
        raise HTTPException(
            status_code=413,
            detail="The selected date range contains too many transactions for one summary.",
        )

    category_page = _list_records(
        client, database, current_user.id, "categories", 200, None
    )
    category_kinds = {
        item["record_id"]: item["data"].get("kind")
        for item in category_page["items"]
    }
    income = Decimal("0.00")
    expenses = Decimal("0.00")
    category_totals: dict[str, Decimal] = {}
    unclassified_count = 0
    count = 0

    for document in transactions:
        data = document.get("data", {})
        if data.get("is_deleted") is True or data.get("currency") != currency:
            continue
        amount = Decimal(str(data["amount"]))
        category_id = data.get("category_id")
        kind = category_kinds.get(category_id)
        if not category_id:
            unclassified_count += 1
        if kind != "transfer":
            if amount > 0:
                income += amount
            elif amount < 0:
                expenses += abs(amount)
        if category_id:
            category_totals[category_id] = (
                category_totals.get(category_id, Decimal("0.00")) + amount
            )
        count += 1

    return FinancialSummary(
        from_date=from_date,
        to_date=to_date,
        currency=currency,
        income=income,
        expenses=expenses,
        net_cash_flow=income - expenses,
        transaction_count=count,
        unclassified_count=unclassified_count,
        category_totals=category_totals,
    )
