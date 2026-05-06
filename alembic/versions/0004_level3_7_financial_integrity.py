"""Level 3.7: financial integrity for linked operations

Revision ID: 0004_level3_7
Revises: 0003_level3_6
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_level3_7'
down_revision = '0003_level3_6'
branch_labels = None
depends_on = None


def _has_table(table_name):
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def _has_column(table_name, column_name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return _has_table(table_name) and any(c['name'] == column_name for c in insp.get_columns(table_name))


def upgrade():
    if not _has_table('debt_payments'):
        op.create_table(
            'debt_payments',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('debt_id', sa.Integer(), sa.ForeignKey('debts.id'), nullable=False),
            sa.Column('wallet_id', sa.Integer(), sa.ForeignKey('wallets.id'), nullable=False),
            sa.Column('transaction_id', sa.Integer(), sa.ForeignKey('transactions.id'), nullable=True),
            sa.Column('amount', sa.Numeric(18, 2), nullable=False),
            sa.Column('currency', sa.String(length=8), nullable=False),
            sa.Column('amount_base', sa.Numeric(18, 2), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_debt_payments_family_id', 'debt_payments', ['family_id'])
        op.create_index('ix_debt_payments_debt_id', 'debt_payments', ['debt_id'])
        op.create_index('ix_debt_payments_transaction_id', 'debt_payments', ['transaction_id'])

    # Best-effort Numeric migration. На PostgreSQL изменит типы; на SQLite batch mode создаст временные таблицы.
    numeric_18_2 = sa.Numeric(18, 2)
    numeric_18_6 = sa.Numeric(18, 6)
    numeric_cols = {
        'wallets': [('balance', numeric_18_2)],
        'exchange_rates': [('rate_to_base', numeric_18_6)],
        'transactions': [('amount', numeric_18_2), ('amount_base', numeric_18_2)],
        'transfers': [('amount_from', numeric_18_2), ('amount_to', numeric_18_2), ('amount_base', numeric_18_2)],
        'debts': [('total_amount', numeric_18_2), ('paid_amount', numeric_18_2), ('total_base', numeric_18_2), ('paid_base', numeric_18_2)],
        'goals': [('target_amount', numeric_18_2), ('current_amount', numeric_18_2)],
        'budgets': [('limit_amount', numeric_18_2), ('limit_base', numeric_18_2)],
        'goal_contributions': [('amount', numeric_18_2)],
    }
    for table, cols in numeric_cols.items():
        if not _has_table(table):
            continue
        with op.batch_alter_table(table) as batch:
            for col_name, col_type in cols:
                if _has_column(table, col_name):
                    batch.alter_column(col_name, type_=col_type, existing_nullable=True)


def downgrade():
    if _has_table('debt_payments'):
        op.drop_index('ix_debt_payments_transaction_id', table_name='debt_payments')
        op.drop_index('ix_debt_payments_debt_id', table_name='debt_payments')
        op.drop_index('ix_debt_payments_family_id', table_name='debt_payments')
        op.drop_table('debt_payments')
