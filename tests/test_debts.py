"""Validation tests for debt-management records."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.finance import DebtCreate, DebtUpdate


def test_debt_create_accepts_valid_personal_debt() -> None:
    debt = DebtCreate(
        creditor="FNB",
        debt_name="Vehicle finance",
        debt_type="vehicle_finance",
        original_amount=Decimal("180000.00"),
        current_balance=Decimal("145000.00"),
        monthly_payment=Decimal("5200.00"),
        interest_rate=Decimal("12.500"),
        currency="ZAR",
    )

    assert debt.current_balance == Decimal("145000.00")
    assert debt.debt_type == "vehicle_finance"


def test_debt_create_rejects_negative_outstanding_balance() -> None:
    with pytest.raises(ValidationError):
        DebtCreate(
            creditor="FNB",
            debt_name="Personal loan",
            debt_type="personal_loan",
            original_amount=Decimal("10000.00"),
            current_balance=Decimal("-1.00"),
        )


def test_debt_update_accepts_zero_balance_for_paid_off_debt() -> None:
    update = DebtUpdate(current_balance=Decimal("0.00"))

    assert update.current_balance == Decimal("0.00")
