"""Level 5.3 PWA, scheduled reminders and financial plan

Revision ID: 0009_level5_3
Revises: 0008_level4_3_2
"""
from alembic import op
import sqlalchemy as sa

revision = '0009_level5_3'
down_revision = '0008_level4_3_2_numeric_cleanup'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scheduled_payments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='UZS'),
        sa.Column('kind', sa.String(length=32), nullable=False, server_default='expense'),
        sa.Column('due_day', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_sent_month', sa.String(length=7)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'financial_plan_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('target_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('current_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='UZS'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('deadline', sa.String(length=20)),
        sa.Column('note', sa.String(length=500)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('financial_plan_items')
    op.drop_table('scheduled_payments')
