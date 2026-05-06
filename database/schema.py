"""Level 4.7 database schema.

All SQLAlchemy engine, metadata, table definitions and shared validation helpers
were moved here from monolith.py. Domain modules import these objects directly.
"""
import re
import secrets
from datetime import datetime, date, timedelta
from typing import Any
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, MetaData, String, Numeric,
    and_, or_, create_engine, func, inspect, select, update, text, delete
)
from sqlalchemy.engine import Engine
from sqlalchemy import Table

from config import BASE_CURRENCY, DATABASE_URL

engine: Engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
metadata = MetaData()

families = Table('families', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(120), nullable=False),
    Column('invite_code', String(24), unique=True, nullable=False),
    Column('base_currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('created_at', DateTime, nullable=False),
)
users = Table('users', metadata,
    Column('id', Integer, primary_key=True),
    Column('telegram_id', BigInteger, unique=True, nullable=False),
    Column('family_id', Integer, ForeignKey('families.id')),
    Column('full_name', String(160)),
    Column('role', String(24), nullable=False, default='admin'),
    Column('created_at', DateTime, nullable=False),
)
wallets = Table('wallets', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('name', String(120), nullable=False),
    Column('currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('balance', Numeric(18, 2), nullable=False, default=0),
    Column('include_in_free_money', Integer, nullable=False, default=1),
    Column('created_at', DateTime, nullable=False),
)
categories = Table('categories', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('name', String(120), nullable=False),
    Column('type', String(16), nullable=False),
    Column('parent_id', Integer, ForeignKey('categories.id')),
    Column('created_at', DateTime, nullable=False),
)
exchange_rates = Table('exchange_rates', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('currency', String(8), nullable=False),
    Column('rate_to_base', Numeric(18, 6), nullable=False),
    Column('updated_at', DateTime, nullable=False),
)
transactions = Table('transactions', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('type', String(16), nullable=False),  # income / expense / transfer_in / transfer_out
    Column('amount', Numeric(18, 2), nullable=False),
    Column('currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('amount_base', Numeric(18, 2), nullable=False, default=0),
    Column('wallet_id', Integer, ForeignKey('wallets.id')),
    Column('category_id', Integer, ForeignKey('categories.id')),
    Column('transfer_id', Integer, ForeignKey('transfers.id')),
    Column('scheduled_payment_id', Integer, ForeignKey('scheduled_payments.id')),
    Column('comment', String(300)),
    Column('created_at', DateTime, nullable=False),
)

transfers = Table('transfers', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('from_wallet_id', Integer, ForeignKey('wallets.id'), nullable=False),
    Column('to_wallet_id', Integer, ForeignKey('wallets.id'), nullable=False),
    Column('amount_from', Numeric(18, 2), nullable=False),
    Column('currency_from', String(8), nullable=False),
    Column('amount_to', Numeric(18, 2), nullable=False),
    Column('currency_to', String(8), nullable=False),
    Column('amount_base', Numeric(18, 2), nullable=False, default=0),
    Column('comment', String(300)),
    Column('created_at', DateTime, nullable=False),
)
debts = Table('debts', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('name', String(160), nullable=False),
    Column('total_amount', Numeric(18, 2), nullable=False),
    Column('paid_amount', Numeric(18, 2), nullable=False, default=0),
    Column('currency', String(8), nullable=False, default='USD'),
    Column('total_base', Numeric(18, 2), nullable=False, default=0),
    Column('paid_base', Numeric(18, 2), nullable=False, default=0),
    Column('comment', String(300)),
    Column('created_at', DateTime, nullable=False),
)
goals = Table('goals', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('name', String(160), nullable=False),
    Column('target_amount', Numeric(18, 2), nullable=False),
    Column('current_amount', Numeric(18, 2), nullable=False, default=0),
    Column('currency', String(8), nullable=False, default='USD'),
    Column('deadline', String(20)),
    Column('created_at', DateTime, nullable=False),
)
budgets = Table('budgets', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('category_id', Integer, ForeignKey('categories.id'), nullable=False),
    Column('month', String(7), nullable=False),
    Column('limit_amount', Numeric(18, 2), nullable=False),
    Column('currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('limit_base', Numeric(18, 2), nullable=False, default=0),
    Column('created_at', DateTime, nullable=False),
)
notification_settings = Table('notification_settings', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('daily_enabled', Integer, nullable=False, default=1),
    Column('budget_alert_enabled', Integer, nullable=False, default=1),
    Column('scheduled_payment_enabled', Integer, nullable=False, default=1),
    Column('created_at', DateTime, nullable=False),
)

# Level 5.4: per-member permission overrides for granular family rights.
family_member_permission_overrides = Table('family_member_permission_overrides', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('permission', String(80), nullable=False),
    Column('allowed', Integer, nullable=False, default=1),
    Column('updated_at', DateTime, nullable=False),
    extend_existing=True,
)




# Level 5.3/5.3.1: scheduled reminders and financial plan tables
scheduled_payment_delivery_log = Table('scheduled_payment_delivery_log', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('schedule_id', Integer, ForeignKey('scheduled_payments.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('telegram_id', BigInteger, nullable=False),
    Column('month', String(7), nullable=False),
    Column('status', String(32), nullable=False, default='sent'),
    Column('error', String(500)),
    Column('sent_at', DateTime, nullable=False),
    extend_existing=True,
)

scheduled_payments = Table('scheduled_payments', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('title', String(160), nullable=False),
    Column('amount', Numeric(18, 2), nullable=False, default=0),
    Column('currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('kind', String(32), nullable=False, default='expense'),
    Column('wallet_id', Integer, ForeignKey('wallets.id')),
    Column('category_id', Integer, ForeignKey('categories.id')),
    Column('auto_create_expense', Integer, nullable=False, default=0),
    Column('last_auto_created_month', String(7)),
    Column('due_day', Integer, nullable=False, default=1),
    Column('enabled', Integer, nullable=False, default=1),
    Column('last_sent_month', String(7)),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)
financial_plan_items = Table('financial_plan_items', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('title', String(160), nullable=False),
    Column('target_amount', Numeric(18, 2), nullable=False, default=0),
    Column('current_amount', Numeric(18, 2), nullable=False, default=0),
    Column('currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('priority', Integer, nullable=False, default=3),
    Column('deadline', String(20)),
    Column('note', String(500)),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)


# Level 5.5: personal AI rules and budget setup wizard profile.
ai_personal_rules = Table('ai_personal_rules', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('title', String(160), nullable=False),
    Column('rule_type', String(40), nullable=False, default='category_limit'),
    Column('category_id', Integer, ForeignKey('categories.id')),
    Column('threshold_amount', Numeric(18, 2), nullable=False, default=0),
    Column('currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('enabled', Integer, nullable=False, default=1),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

budget_wizard_profiles = Table('budget_wizard_profiles', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('monthly_income', Numeric(18, 2), nullable=False, default=0),
    Column('base_currency', String(8), nullable=False, default=BASE_CURRENCY),
    Column('rent_amount', Numeric(18, 2), nullable=False, default=0),
    Column('kindergarten_amount', Numeric(18, 2), nullable=False, default=0),
    Column('installment_amount', Numeric(18, 2), nullable=False, default=0),
    Column('food_amount', Numeric(18, 2), nullable=False, default=0),
    Column('transport_amount', Numeric(18, 2), nullable=False, default=0),
    Column('savings_target_percent', Integer, nullable=False, default=10),
    Column('updated_at', DateTime, nullable=False),
    extend_existing=True,
)

# Level 5.4.1: full family permission matrix is kept in one place.
FAMILY_PERMISSIONS = {
    'manage_family',
    'manage_structure',
    'manage_wallets',
    'manage_categories',
    'manage_rates',
    'manage_budget',
    'manage_debt',
    'manage_goals',
    'manage_schedules',
    'manage_financial_plan',
    'add_transaction',
    'transfer',
    'export',
    'view_ai_analysis',
    'manage_ai_rules',
}
ROLE_PERMISSIONS = {
    'admin': set(FAMILY_PERMISSIONS),
    'husband': {
        'manage_structure', 'manage_wallets', 'manage_categories', 'manage_rates',
        'manage_budget', 'manage_debt', 'manage_goals', 'manage_schedules',
        'manage_financial_plan', 'add_transaction', 'transfer', 'export',
        'view_ai_analysis', 'manage_ai_rules',
    },
    'wife': {
        'manage_structure', 'manage_wallets', 'manage_categories', 'manage_rates',
        'manage_budget', 'manage_debt', 'manage_goals', 'manage_schedules',
        'manage_financial_plan', 'add_transaction', 'transfer', 'export',
        'view_ai_analysis', 'manage_ai_rules',
    },
    'member': {'add_transaction', 'transfer'},
}
ALLOWED_ROLES = set(ROLE_PERMISSIONS)
ALLOWED_CURRENCIES = {'UZS', 'USD', 'KRW'}
ALLOWED_TX_TYPES = {'income', 'expense'}


def _now() -> datetime:
    return datetime.now()

def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

def _row(row):
    return {k: _jsonable(v) for k, v in dict(row._mapping).items()} if row else None

def _rows(rows):
    return [{k: _jsonable(v) for k, v in dict(r._mapping).items()} for r in rows]

def _new_code() -> str:
    return secrets.token_urlsafe(6).replace('-', '').replace('_', '')[:8].upper()

def _clean_text(value: Any, max_len: int = 300) -> str:
    value = str(value or '').strip()
    return value[:max_len]

def _money(value: Any, field='Сумма') -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception:
        raise ValueError(f'{field} должна быть числом')
    if amount <= 0:
        raise ValueError(f'{field} должна быть больше нуля')
    if amount > Decimal('1000000000000000'):
        raise ValueError(f'{field} слишком большая')
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def _rate(value: Any, field='Курс') -> Decimal:
    try:
        amount = Decimal(str(value))
    except Exception:
        raise ValueError(f'{field} должен быть числом')
    if amount <= 0:
        raise ValueError(f'{field} должен быть больше нуля')
    return amount.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

def _num(value: Any) -> float:
    return float(value or 0)

def validate_amount(amount: float, field='Сумма') -> Decimal:
    return _money(amount, field)

def validate_currency(currency: str) -> str:
    currency = str(currency or BASE_CURRENCY).upper().strip()
    if currency not in ALLOWED_CURRENCIES:
        raise ValueError('Неподдерживаемая валюта')
    return currency

def validate_month(month: str | None) -> str:
    month = month or date.today().strftime('%Y-%m')
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('Месяц должен быть в формате YYYY-MM')
    return month

def _role_has_permission(user: dict, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.get('role', 'member'), set())

def has_permission(user: dict, permission: str) -> bool:
    """Role permission + Level 5.4 per-member override.

    Overrides are intentionally checked here, so all legacy require_permission()
    calls automatically respect granular family rights.
    """
    allowed = _role_has_permission(user, permission)
    try:
        uid = int(user.get('id') or 0)
        family_id = int(user.get('family_id') or 0)
        if uid and family_id and inspect(engine).has_table('family_member_permission_overrides'):
            with engine.begin() as conn:
                row = conn.execute(select(family_member_permission_overrides.c.allowed).where(and_(
                    family_member_permission_overrides.c.family_id == family_id,
                    family_member_permission_overrides.c.user_id == uid,
                    family_member_permission_overrides.c.permission == permission,
                )).order_by(family_member_permission_overrides.c.id.desc()).limit(1)).first()
            if row is not None:
                return bool(row._mapping['allowed'])
    except Exception:
        # Permission checks must stay safe during initial migrations.
        pass
    return allowed

def require_permission(user: dict, permission: str):
    if not has_permission(user, permission):
        raise ValueError('Недостаточно прав для этого действия')

def _has_column(table_name: str, column_name: str) -> bool:
    try:
        return any(c['name'] == column_name for c in inspect(engine).get_columns(table_name))
    except Exception:
        return False







# Level 3.6+ tables moved from monolith.py in Level 4.7
audit_logs = Table('audit_logs', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('action', String(64), nullable=False),
    Column('entity_type', String(64), nullable=False),
    Column('entity_id', Integer),
    Column('details', String(1000)),
    Column('resolved_at', DateTime),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

goal_contributions = Table('goal_contributions', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('goal_id', Integer, ForeignKey('goals.id'), nullable=False),
    Column('wallet_id', Integer, ForeignKey('wallets.id'), nullable=False),
    Column('transaction_id', Integer, ForeignKey('transactions.id')),
    Column('amount', Numeric(18, 2), nullable=False),
    Column('currency', String(8), nullable=False),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

debt_payments = Table('debt_payments', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('user_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('debt_id', Integer, ForeignKey('debts.id'), nullable=False),
    Column('wallet_id', Integer, ForeignKey('wallets.id'), nullable=False),
    Column('transaction_id', Integer, ForeignKey('transactions.id')),
    Column('amount', Numeric(18, 2), nullable=False),
    Column('currency', String(8), nullable=False),
    Column('amount_base', Numeric(18, 2), nullable=False, default=0),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

admin_audit_logs = Table('admin_audit_logs', metadata,
    Column('id', Integer, primary_key=True),
    Column('admin_label', String(120)),
    Column('ip_address', String(80)),
    Column('action', String(80), nullable=False),
    Column('entity_type', String(80)),
    Column('entity_id', Integer),
    Column('details', String(2000)),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

# Single source of truth for blocking: users.is_blocked.
if 'is_blocked' not in users.c:
    users.append_column(Column('is_blocked', Integer, nullable=False, default=0))

admin_sessions = Table('admin_sessions', metadata,
    Column('id', String(128), primary_key=True),
    Column('csrf', String(128), nullable=False),
    Column('is_superadmin', Integer, nullable=False, default=0),
    Column('ip_address', String(64)),
    Column('expires_at', DateTime, nullable=False),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

budget_notification_events = Table('budget_notification_events', metadata,
    Column('id', Integer, primary_key=True),
    Column('family_id', Integer, ForeignKey('families.id'), nullable=False),
    Column('budget_id', Integer, ForeignKey('budgets.id'), nullable=False),
    Column('percent', Numeric(18, 2), nullable=False, default=0),
    Column('created_at', DateTime, nullable=False),
    extend_existing=True,
)

def _d(value: Any, default='0') -> Decimal:
    return Decimal(str(value if value is not None else default))

__all__ = [name for name in globals() if not name.startswith('__')]
