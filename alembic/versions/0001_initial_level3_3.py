"""initial level 3.3 schema

Revision ID: 0001_initial_level3_3
Revises:
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_initial_level3_3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('families',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('invite_code', sa.String(length=24), nullable=False, unique=True),
        sa.Column('base_currency', sa.String(length=8), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id')),
        sa.Column('full_name', sa.String(length=160)),
        sa.Column('role', sa.String(length=24), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('wallets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('balance', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('exchange_rates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('rate_to_base', sa.Numeric(18, 6), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_table('transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('amount_base', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('wallet_id', sa.Integer(), sa.ForeignKey('wallets.id')),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id')),
        sa.Column('comment', sa.String(length=300)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('debts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('total_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('paid_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('total_base', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('paid_base', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('comment', sa.String(length=300)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('goals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('name', sa.String(length=160), nullable=False),
        sa.Column('target_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('current_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('deadline', sa.String(length=20)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('budgets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('limit_amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('currency', sa.String(length=8), nullable=False),
        sa.Column('limit_base', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table('notification_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('daily_enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('budget_alert_enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    for table in ['notification_settings','budgets','goals','debts','transactions','exchange_rates','categories','wallets','users','families']:
        op.drop_table(table)
