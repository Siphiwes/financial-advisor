"""Authenticated financial account, transaction and planning APIs."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user, require_financial_data_enabled
from app.schemas.auth import AuthenticatedUser
from app.schemas.finance import (
    BudgetCreate,
    BudgetProgressResponse,
    BudgetResponse,
    BudgetUpdate,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    FinancialAccountCreate,
    FinancialAccountResponse,
    FinancialAccountUpdate,
    FinancialSummaryResponse,
    GoalContributionCreate,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
    RecurringPaymentCandidate,
)
from app.services import finance

router = APIRouter(
    prefix="/api/v1",
    tags=["personal finance"],
    dependencies=[Depends(require_financial_data_enabled)],
)
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail="The requested record was not found.")


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("/accounts", response_model=list[FinancialAccountResponse])
def read_accounts(current_user: CurrentUser) -> list[dict]:
    return finance.list_financial_accounts(current_user)


@router.post(
    "/accounts",
    response_model=FinancialAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_account(payload: FinancialAccountCreate, current_user: CurrentUser) -> dict:
    return finance.create_financial_account(current_user, payload)


@router.get("/accounts/{account_id}", response_model=FinancialAccountResponse)
def read_account(account_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.get_financial_account(current_user.id, account_id, active=False)
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/accounts/{account_id}", response_model=FinancialAccountResponse)
def edit_account(
    account_id: str,
    payload: FinancialAccountUpdate,
    current_user: CurrentUser,
) -> dict:
    try:
        return finance.update_financial_account(
            current_user, account_id, payload.model_dump(exclude_unset=True)
        )
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/accounts/{account_id}", response_model=FinancialAccountResponse)
def deactivate_account(account_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.update_financial_account(
            current_user, account_id, {"is_active": False}
        )
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/transactions", response_model=TransactionListResponse)
def read_transactions(
    current_user: CurrentUser,
    account_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    category: str | None = Query(default=None, max_length=80),
    search: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
) -> dict:
    try:
        items, has_more = finance.list_transactions(
            current_user,
            account_id=account_id,
            from_date=from_date,
            to_date=to_date,
            category=category,
            search=search,
            limit=limit,
            offset=offset,
        )
    except finance.FinanceValidationError as exc:
        raise _invalid(exc) from exc
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_transaction(payload: TransactionCreate, current_user: CurrentUser) -> dict:
    try:
        return finance.create_manual_transaction(current_user, payload)
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def read_transaction(transaction_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.get_transaction(current_user, transaction_id)
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.patch("/transactions/{transaction_id}", response_model=TransactionResponse)
def edit_transaction(
    transaction_id: str,
    payload: TransactionUpdate,
    current_user: CurrentUser,
) -> dict:
    try:
        return finance.update_transaction(
            current_user,
            transaction_id,
            payload.model_dump(exclude_unset=True),
        )
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/transactions/{transaction_id}", response_model=TransactionResponse)
def remove_transaction(transaction_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.delete_transaction(current_user, transaction_id)
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/categories", response_model=list[CategoryResponse])
def read_categories(current_user: CurrentUser) -> list[dict]:
    return finance.list_categories(current_user)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_category(payload: CategoryCreate, current_user: CurrentUser) -> dict:
    try:
        return finance.create_category(current_user, payload.name, payload.kind)
    except finance.FinanceValidationError as exc:
        raise _invalid(exc) from exc


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def edit_category(
    category_id: str,
    payload: CategoryUpdate,
    current_user: CurrentUser,
) -> dict:
    try:
        return finance.update_category(
            current_user, category_id, payload.model_dump(exclude_unset=True)
        )
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc
    except finance.FinanceValidationError as exc:
        raise _invalid(exc) from exc


@router.get("/budgets/progress", response_model=list[BudgetProgressResponse])
def read_budget_progress(current_user: CurrentUser) -> list[dict]:
    return finance.list_budget_progress(current_user)


@router.get("/budgets", response_model=list[BudgetResponse])
def read_budgets(current_user: CurrentUser) -> list[dict]:
    return finance.list_budgets(current_user)


@router.post(
    "/budgets",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_budget(payload: BudgetCreate, current_user: CurrentUser) -> dict:
    return finance.create_budget(current_user, payload)


@router.patch("/budgets/{budget_id}", response_model=BudgetResponse)
def edit_budget(
    budget_id: str,
    payload: BudgetUpdate,
    current_user: CurrentUser,
) -> dict:
    try:
        return finance.update_budget(
            current_user, budget_id, payload.model_dump(exclude_unset=True)
        )
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/budgets/{budget_id}", response_model=BudgetResponse)
def remove_budget(budget_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.update_budget(current_user, budget_id, {"is_active": False})
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/goals/{goal_id}", response_model=GoalResponse)
def read_goal(goal_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.get_goal(current_user, goal_id)
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/goals/{goal_id}/contributions",
    response_model=GoalResponse,
)
def add_goal_contribution(
    goal_id: str,
    payload: GoalContributionCreate,
    current_user: CurrentUser,
) -> dict:
    try:
        return finance.add_goal_contribution(current_user, goal_id, payload)
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc
    except finance.FinanceValidationError as exc:
        raise _invalid(exc) from exc


@router.get("/goals", response_model=list[GoalResponse])
def read_goals(current_user: CurrentUser) -> list[dict]:
    return finance.list_goals(current_user)


@router.post(
    "/goals",
    response_model=GoalResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_goal(payload: GoalCreate, current_user: CurrentUser) -> dict:
    return finance.create_goal(current_user, payload)


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def edit_goal(
    goal_id: str,
    payload: GoalUpdate,
    current_user: CurrentUser,
) -> dict:
    try:
        return finance.update_goal(
            current_user, goal_id, payload.model_dump(exclude_unset=True)
        )
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.delete("/goals/{goal_id}", response_model=GoalResponse)
def remove_goal(goal_id: str, current_user: CurrentUser) -> dict:
    try:
        return finance.update_goal(current_user, goal_id, {"is_active": False})
    except finance.FinanceRecordNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get(
    "/analytics/recurring-payments",
    response_model=list[RecurringPaymentCandidate],
)
def read_recurring_payment_candidates(current_user: CurrentUser) -> list[dict]:
    return finance.recurring_payment_candidates(current_user)


@router.get("/analytics/summary", response_model=FinancialSummaryResponse)
def read_financial_summary(
    current_user: CurrentUser,
    from_date: date | None = None,
    to_date: date | None = None,
) -> FinancialSummaryResponse:
    try:
        return finance.financial_summary(
            current_user, from_date=from_date, to_date=to_date
        )
    except finance.FinanceValidationError as exc:
        raise _invalid(exc) from exc
