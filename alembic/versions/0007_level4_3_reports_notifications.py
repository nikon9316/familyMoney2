"""Level 4.3 reports, forecasts and notification cooldown

Revision ID: 0007_level4_3
Revises: 0006_level4_2
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0007_level4_3'
down_revision = '0006_level4_2'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'budget_notification_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('budget_id', sa.Integer(), sa.ForeignKey('budgets.id'), nullable=False),
        sa.Column('percent', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_budget_notification_events_family_budget_created', 'budget_notification_events', ['family_id', 'budget_id', 'created_at'])

def downgrade():
    op.drop_index('ix_budget_notification_events_family_budget_created', table_name='budget_notification_events')
    op.drop_table('budget_notification_events')
