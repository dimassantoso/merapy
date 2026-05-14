from merapy.helper.string_case import to_camel, to_kebab, to_pascal, to_snake


def test_to_snake() -> None:
    assert to_snake("ExpenseTracker") == "expense_tracker"
    assert to_snake("expense-tracker") == "expense_tracker"
    assert to_snake("expenseTracker") == "expense_tracker"
    assert to_snake("expense_tracker") == "expense_tracker"


def test_to_kebab() -> None:
    assert to_kebab("ExpenseTracker") == "expense-tracker"
    assert to_kebab("expense_tracker") == "expense-tracker"


def test_to_pascal() -> None:
    assert to_pascal("expense_tracker") == "ExpenseTracker"
    assert to_pascal("expense-tracker") == "ExpenseTracker"


def test_to_camel() -> None:
    assert to_camel("expense_tracker") == "expenseTracker"
    assert to_camel("expense-tracker") == "expenseTracker"
