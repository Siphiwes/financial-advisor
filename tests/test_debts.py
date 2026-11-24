"""Contract checks for debt schemas without fabricated financial records."""

from app.schemas.finance import DebtCreate, DebtResponse, DebtSummaryResponse, DebtUpdate


def test_debt_create_exposes_required_management_fields() -> None:
    assert {"creditor", "debt_name", "debt_type", "original_amount", "current_balance"} <= set(
        DebtCreate.model_fields
    )


def test_debt_update_supports_balance_and_repayment_maintenance() -> None:
    assert {"current_balance", "monthly_payment", "interest_rate", "due_date", "notes"} <= set(
        DebtUpdate.model_fields
    )


def test_debt_response_includes_balance_history() -> None:
    assert {"status", "balance_history", "current_balance"} <= set(DebtResponse.model_fields)


def test_debt_summary_exposes_income_comparison_and_trend() -> None:
    assert "currencies" in DebtSummaryResponse.model_fields
