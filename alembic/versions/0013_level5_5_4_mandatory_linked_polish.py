"""Level 5.5.4 mandatory linked transaction polish

Revision ID: 0013_level5_5_4
Revises: 0012_level5_5_1
"""
from alembic import op
import sqlalchemy as sa

revision = '0013_level5_5_4'
down_revision = '0012_level5_5_1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('wallets', sa.Column('include_in_free_money', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('audit_logs', sa.Column('resolved_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('audit_logs', 'resolved_at')
    op.drop_column('wallets', 'include_in_free_money')
