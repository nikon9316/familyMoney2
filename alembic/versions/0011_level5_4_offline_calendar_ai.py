"""Level 5.4 offline, calendar, granular permissions and AI analysis

Revision ID: 0011_level5_4
Revises: 0010_level5_3_1
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa

revision = '0011_level5_4'
down_revision = '0010_level5_3_1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'family_member_permission_overrides',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('permission', sa.String(length=80), nullable=False),
        sa.Column('allowed', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_family_member_permission_unique', 'family_member_permission_overrides', ['family_id', 'user_id', 'permission'], unique=True)


def downgrade():
    op.drop_index('ix_family_member_permission_unique', table_name='family_member_permission_overrides')
    op.drop_table('family_member_permission_overrides')
