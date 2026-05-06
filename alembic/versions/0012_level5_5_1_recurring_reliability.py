"""Level 5.5.1 recurring reliability and linked mandatory payments

Revision ID: 0012_level5_5_1
Revises: 0011_level5_4
"""
from alembic import op
import sqlalchemy as sa

revision = '0012_level5_5_1'
down_revision = '0011_level5_4'
branch_labels = None
depends_on = None


def upgrade():
    # Level 5.5 structures that are required by production Alembic upgrades.
    op.add_column('categories', sa.Column('parent_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True))
    op.add_column('scheduled_payments', sa.Column('wallet_id', sa.Integer(), sa.ForeignKey('wallets.id'), nullable=True))
    op.add_column('scheduled_payments', sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True))
    op.add_column('scheduled_payments', sa.Column('auto_create_expense', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scheduled_payments', sa.Column('last_auto_created_month', sa.String(length=7), nullable=True))
    op.add_column('transactions', sa.Column('scheduled_payment_id', sa.Integer(), sa.ForeignKey('scheduled_payments.id'), nullable=True))

    op.create_table(
        'ai_personal_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('rule_type', sa.String(length=40), nullable=False, server_default='category_limit'),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('threshold_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=8), nullable=False, server_default='UZS'),
        sa.Column('enabled', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'budget_wizard_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('monthly_income', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('base_currency', sa.String(length=8), nullable=False, server_default='UZS'),
        sa.Column('rent_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('kindergarten_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('installment_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('food_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('transport_amount', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('savings_target_percent', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('family_id', name='uq_budget_wizard_family'),
    )


def downgrade():
    op.drop_table('budget_wizard_profiles')
    op.drop_table('ai_personal_rules')
    op.drop_column('transactions', 'scheduled_payment_id')
    op.drop_column('scheduled_payments', 'last_auto_created_month')
    op.drop_column('scheduled_payments', 'auto_create_expense')
    op.drop_column('scheduled_payments', 'category_id')
    op.drop_column('scheduled_payments', 'wallet_id')
    op.drop_column('categories', 'parent_id')
