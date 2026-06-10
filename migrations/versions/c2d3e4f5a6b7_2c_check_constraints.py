"""2c: data-integrity CHECK constraints

Adds SQL CHECK constraints so direct model writes (which bypass the service-layer
guards) can't store invalid rows. DecimalText columns are TEXT, so sign checks cast
to REAL — fine for sign comparisons, precision is irrelevant. Applied via
batch_alter_table (SQLite rebuilds the table).

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-10 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECKS = {
    'expenses': [
        ('ck_expense_amount_pos', 'CAST(amount_inr AS REAL) > 0'),
    ],
    'budgets': [
        ('ck_budget_month_range', 'month BETWEEN 1 AND 12'),
        ('ck_budget_limit_pos', 'CAST(limit_amount_inr AS REAL) > 0'),
    ],
    'transactions': [
        ('ck_transaction_units_nonneg', 'CAST(units AS REAL) >= 0'),
        ('ck_transaction_price_nonneg', 'CAST(price_per_unit AS REAL) >= 0'),
    ],
    'fd_details': [
        ('ck_fd_principal_pos', 'CAST(principal AS REAL) > 0'),
        ('ck_fd_maturity_after_start', 'maturity_date >= start_date'),
    ],
}


def upgrade() -> None:
    """Upgrade schema."""
    for table, checks in _CHECKS.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name, condition in checks:
                batch_op.create_check_constraint(name, condition)


def downgrade() -> None:
    """Downgrade schema."""
    for table, checks in _CHECKS.items():
        with op.batch_alter_table(table, schema=None) as batch_op:
            for name, _ in checks:
                batch_op.drop_constraint(name, type_='check')
