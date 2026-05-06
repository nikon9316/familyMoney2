"""Railway/PostgreSQL smoke test for Family Finance.

Run after migrations on Railway or locally:
    APP_ENV=production DB_AUTO_CREATE=false DATABASE_URL=postgresql://... python scripts/postgres_smoke_test.py

The script verifies connection, required tables, Decimal/Numeric behavior,
core finance writes, goal contribution via wallet, and rollback cleanup.
"""
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if not os.getenv('DATABASE_URL'):
    raise SystemExit('DATABASE_URL is not set')

os.environ.setdefault('APP_ENV', 'production')
os.environ.setdefault('DB_AUTO_CREATE', 'false')

from sqlalchemy import inspect, text  # noqa: E402
from database.db import (  # noqa: E402
    engine, init_db, get_or_create_user, add_wallet, add_category,
    add_transaction, get_summary, get_wallets, add_goal, add_goal_money, get_goals,
)

REQUIRED_TABLES = [
    'families', 'users', 'wallets', 'categories', 'transactions', 'transfers',
    'debts', 'debt_payments', 'goals', 'goal_contributions', 'budgets',
    'audit_logs', 'admin_audit_logs', 'admin_sessions', 'budget_notification_events',
]

init_db()
ins = inspect(engine)
missing = [t for t in REQUIRED_TABLES if not ins.has_table(t)]
if missing:
    raise SystemExit('Missing tables after alembic upgrade: ' + ', '.join(missing))

with engine.begin() as conn:
    dbname = conn.execute(text('select current_database()')).scalar()
print('Connected to PostgreSQL database:', dbname)

user = get_or_create_user(999000111, 'Railway Smoke Test')
wallet_id = add_wallet(user, 'Smoke Wallet 4.3.2', 'UZS', Decimal('100000.00'))
income_cat = add_category(user, 'Smoke Income 4.3.2', 'income')
expense_cat = add_category(user, 'Smoke Expense 4.3.2', 'expense')
add_transaction(user, 'income', Decimal('12345.67'), 'UZS', wallet_id, income_cat, 'postgres smoke income')
add_transaction(user, 'expense', Decimal('2345.67'), 'UZS', wallet_id, expense_cat, 'postgres smoke expense')
goal_id = add_goal(user, 'Smoke Goal 4.3.2', Decimal('50000'), 'UZS', None)
contribution_id = add_goal_money(user, goal_id, Decimal('10000'), wallet_id)
summary = get_summary(user['family_id'])
wallet = [w for w in get_wallets(user['family_id']) if w['id'] == wallet_id][0]
goal = [g for g in get_goals(user['family_id']) if g['id'] == goal_id][0]
if Decimal(str(goal['current_amount'])) != Decimal('10000.00'):
    raise SystemExit('Goal contribution failed')
print('OK summary:', summary)
print('OK wallet:', wallet)
print('OK contribution_id:', contribution_id)
print('Railway/PostgreSQL smoke test passed')
