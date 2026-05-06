"""Level 3.4: financial architecture fixes

Revision ID: 0002_level3_4
Revises: 0001_initial_level3_3
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_level3_4'
down_revision = '0001_initial_level3_3'
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return any(c['name'] == column_name for c in insp.get_columns(table_name))


def _has_table(table_name):
    bind = op.get_bind()
    return sa.inspect(bind).has_table(table_name)


def upgrade():
    if not _has_table('transfers'):
        op.create_table(
            'transfers',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('from_wallet_id', sa.Integer(), sa.ForeignKey('wallets.id'), nullable=False),
            sa.Column('to_wallet_id', sa.Integer(), sa.ForeignKey('wallets.id'), nullable=False),
            sa.Column('amount_from', sa.Numeric(18, 2), nullable=False),
            sa.Column('currency_from', sa.String(8), nullable=False),
            sa.Column('amount_to', sa.Numeric(18, 2), nullable=False),
            sa.Column('currency_to', sa.String(8), nullable=False),
            sa.Column('amount_base', sa.Numeric(18, 2), nullable=False, server_default='0'),
            sa.Column('comment', sa.String(300)),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
    if _has_table('transactions') and not _has_column('transactions', 'transfer_id'):
        op.add_column('transactions', sa.Column('transfer_id', sa.Integer(), nullable=True))


def downgrade():
    if _has_table('transactions') and _has_column('transactions', 'transfer_id'):
        op.drop_column('transactions', 'transfer_id')
    if _has_table('transfers'):
        op.drop_table('transfers')
