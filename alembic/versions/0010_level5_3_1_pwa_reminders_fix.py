"""Level 5.3.1 PWA and reminders fix

Revision ID: 0010_level5_3_1
Revises: 0009_level5_3
"""
from alembic import op
import sqlalchemy as sa

revision = '0010_level5_3_1'
down_revision = '0009_level5_3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notification_settings', sa.Column('scheduled_payment_enabled', sa.Integer(), nullable=False, server_default='1'))
    op.create_table(
        'scheduled_payment_delivery_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('family_id', sa.Integer(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('schedule_id', sa.Integer(), sa.ForeignKey('scheduled_payments.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='sent'),
        sa.Column('error', sa.String(length=500)),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_scheduled_delivery_month', 'scheduled_payment_delivery_log', ['schedule_id', 'user_id', 'month', 'status'])


def downgrade():
    op.drop_index('ix_scheduled_delivery_month', table_name='scheduled_payment_delivery_log')
    op.drop_table('scheduled_payment_delivery_log')
    op.drop_column('notification_settings', 'scheduled_payment_enabled')
