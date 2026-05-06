"""level4_1_product_admin_compensating_undo

Revision ID: 0005_level4_1
Revises: 0004_level3_7
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_level4_1'
down_revision = '0004_level3_7'
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c['name'] == column_name for c in inspector.get_columns(table_name))


def upgrade():
    if not _has_column('users', 'is_blocked'):
        op.add_column('users', sa.Column('is_blocked', sa.Integer(), nullable=False, server_default='0'))
    if not _has_column('transactions', 'undo_of_audit_id'):
        op.add_column('transactions', sa.Column('undo_of_audit_id', sa.Integer(), nullable=True))
    if not _has_column('transfers', 'undo_of_audit_id'):
        op.add_column('transfers', sa.Column('undo_of_audit_id', sa.Integer(), nullable=True))


def downgrade():
    # SQLite does not support dropping columns safely in older versions; keep as no-op for MVP safety.
    pass
