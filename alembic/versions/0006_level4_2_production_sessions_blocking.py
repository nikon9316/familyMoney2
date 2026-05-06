"""level4_2_production_sessions_blocking

Revision ID: 0006_level4_2
Revises: 0005_level4_1
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0006_level4_2'
down_revision = '0005_level4_1'
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return any(c['name'] == column_name for c in inspector.get_columns(table_name))


def upgrade():
    # Level 4.2 chooses users.is_blocked as the single source of truth for blocking.
    if _has_table('users') and not _has_column('users', 'is_blocked'):
        op.add_column('users', sa.Column('is_blocked', sa.Integer(), nullable=False, server_default='0'))


    if not _has_table('admin_audit_logs'):
        op.create_table(
            'admin_audit_logs',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('admin_label', sa.String(length=120), nullable=True),
            sa.Column('ip_address', sa.String(length=80), nullable=True),
            sa.Column('action', sa.String(length=80), nullable=False),
            sa.Column('entity_type', sa.String(length=80), nullable=True),
            sa.Column('entity_id', sa.Integer(), nullable=True),
            sa.Column('details', sa.String(length=2000), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )

    if not _has_table('admin_sessions'):
        op.create_table(
            'admin_sessions',
            sa.Column('id', sa.String(length=128), primary_key=True),
            sa.Column('csrf', sa.String(length=128), nullable=False),
            sa.Column('is_superadmin', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('ip_address', sa.String(length=64), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_admin_sessions_expires_at', 'admin_sessions', ['expires_at'])


def downgrade():
    if _has_table('admin_sessions'):
        try:
            op.drop_index('ix_admin_sessions_expires_at', table_name='admin_sessions')
        except Exception:
            pass
        op.drop_table('admin_sessions')
    # Keep users.is_blocked on downgrade to avoid losing operational security data.
