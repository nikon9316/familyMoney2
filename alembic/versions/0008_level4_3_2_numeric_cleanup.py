"""level 4.3.4 Alembic chain and Numeric cleanup

Revision ID: 0008_level4_3_2_numeric_cleanup
Revises: 0007_level4_3
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0008_level4_3_2_numeric_cleanup'
down_revision = '0007_level4_3'
branch_labels = None
depends_on = None

MONEY = sa.Numeric(18, 2)
RATE = sa.Numeric(18, 6)


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(c['name'] == column_name for c in sa.inspect(op.get_bind()).get_columns(table_name))


def _alter_numeric(table: str, column: str, type_, nullable=False, default=None):
    if not _has_column(table, column):
        return
    with op.batch_alter_table(table) as batch:
        batch.alter_column(
            column,
            existing_type=sa.Float(),
            type_=type_,
            existing_nullable=nullable,
            server_default=default,
        )


def upgrade():
    money_columns = [
        ('wallets', 'balance', '0'),
        ('transactions', 'amount', None),
        ('transactions', 'amount_base', '0'),
        ('debts', 'total_amount', None),
        ('debts', 'paid_amount', '0'),
        ('debts', 'total_base', '0'),
        ('debts', 'paid_base', '0'),
        ('goals', 'target_amount', None),
        ('goals', 'current_amount', '0'),
        ('budgets', 'limit_amount', None),
        ('budgets', 'limit_base', '0'),
        ('transfers', 'amount_from', None),
        ('transfers', 'amount_to', None),
        ('debt_payments', 'amount', None),
        ('debt_payments', 'amount_base', '0'),
        ('goal_contributions', 'amount', None),
        ('goal_contributions', 'amount_base', '0'),
        ('budget_notification_events', 'percent', '0'),
    ]
    for table, column, default in money_columns:
        _alter_numeric(table, column, MONEY, default=default)
    _alter_numeric('exchange_rates', 'rate_to_base', RATE, default='1')


def downgrade():
    # Conservative by design: converting exact money columns back to Float is not safe.
    # Leave schema as Numeric; downgrade path is intentionally not destructive.
    return
