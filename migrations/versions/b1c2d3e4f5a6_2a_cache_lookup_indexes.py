"""2a: composite indexes for cache/holding lookups

Adds covering composite indexes so the hot lookups become index scans without a
sort step:
  - prices_cache(investment_id, fetched_at)  -> latest-price lookup
  - transactions(investment_id, date)        -> per-investment holding/date queries
  - expenses(category_id, date)              -> BudgetService spent-in-month

Revision ID: b1c2d3e4f5a6
Revises: ac8711fd3f88
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'ac8711fd3f88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_prices_cache_inv_fetched', 'prices_cache', ['investment_id', 'fetched_at']
    )
    op.create_index(
        'ix_transactions_inv_date', 'transactions', ['investment_id', 'date']
    )
    op.create_index(
        'ix_expenses_category_date', 'expenses', ['category_id', 'date']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_expenses_category_date', table_name='expenses')
    op.drop_index('ix_transactions_inv_date', table_name='transactions')
    op.drop_index('ix_prices_cache_inv_fetched', table_name='prices_cache')
