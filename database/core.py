"""Level 4.7 legacy implementation core.

Implementation functions are kept here temporarily while public access is routed
through domain modules and db.py. Table definitions no longer live here.
"""
from database.schema import *  # noqa: F401,F403
import json as _json_l40
import re as _re_l40

def _create_default_data(conn, family_id: int):
    now = _now()
    conn.execute(wallets.insert(), [
        {'family_id': family_id, 'name': 'Наличные', 'currency': BASE_CURRENCY, 'balance': 0, 'include_in_free_money': 1, 'created_at': now},
        {'family_id': family_id, 'name': 'Карта Александр', 'currency': BASE_CURRENCY, 'balance': 0, 'include_in_free_money': 1, 'created_at': now},
        {'family_id': family_id, 'name': 'Карта супруги', 'currency': BASE_CURRENCY, 'balance': 0, 'include_in_free_money': 1, 'created_at': now},
        {'family_id': family_id, 'name': 'Доллары', 'currency': 'USD', 'balance': 0, 'include_in_free_money': 1, 'created_at': now},
        {'family_id': family_id, 'name': 'Воны', 'currency': 'KRW', 'balance': 0, 'include_in_free_money': 1, 'created_at': now},
    ])
    conn.execute(categories.insert(), [
        {'family_id': family_id, 'name': 'Зарплата', 'type': 'income', 'created_at': now},
        {'family_id': family_id, 'name': 'Подработка', 'type': 'income', 'created_at': now},
        {'family_id': family_id, 'name': 'Подарки', 'type': 'income', 'created_at': now},
        {'family_id': family_id, 'name': 'Продукты', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Дом / квартира', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Дети', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Транспорт', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Связь', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Долги', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Инвестиции', 'type': 'expense', 'created_at': now},
        {'family_id': family_id, 'name': 'Прочее', 'type': 'expense', 'created_at': now},
    ])
    conn.execute(exchange_rates.insert(), [
        {'family_id': family_id, 'currency': BASE_CURRENCY, 'rate_to_base': 1, 'updated_at': now},
        {'family_id': family_id, 'currency': 'USD', 'rate_to_base': 12500, 'updated_at': now},
        {'family_id': family_id, 'currency': 'KRW', 'rate_to_base': 9.2, 'updated_at': now},
    ])


def get_or_create_user(telegram_id: int, full_name: str):
    full_name = _clean_text(full_name, 160) or 'Пользователь'
    with engine.begin() as conn:
        row = conn.execute(select(users).where(users.c.telegram_id == telegram_id)).first()
        if row:
            return _row(row)
        fam_id = conn.execute(families.insert().values(
            name=f'Семья {full_name}', invite_code=_new_code(), base_currency=BASE_CURRENCY, created_at=_now()
        )).inserted_primary_key[0]
        uid = conn.execute(users.insert().values(
            telegram_id=telegram_id, family_id=fam_id, full_name=full_name, role='admin', created_at=_now()
        )).inserted_primary_key[0]
        _create_default_data(conn, fam_id)
        conn.execute(notification_settings.insert().values(
            family_id=fam_id, user_id=uid, daily_enabled=1, budget_alert_enabled=1, scheduled_payment_enabled=1, created_at=_now()
        ))
        return _row(conn.execute(select(users).where(users.c.id == uid)).first())


def get_family(family_id: int):
    with engine.begin() as conn:
        return _row(conn.execute(select(families).where(families.c.id == family_id)).first())

def get_members(family_id: int):
    with engine.begin() as conn:
        return _rows(conn.execute(select(users.c.id, users.c.full_name, users.c.role, users.c.telegram_id)
                                  .where(users.c.family_id == family_id).order_by(users.c.id)))

def join_family(current_user: dict, invite_code: str, role='wife'):
    """Присоединение по invite_code. ВАЖНО: новый пользователь НЕ обязан иметь manage_family.
    Чтобы нельзя было самоназначить admin, роль при входе ограничена wife/member.
    """
    role = role if role in {'wife', 'husband', 'member'} else 'member'
    invite_code = _clean_text(invite_code, 24).upper()
    with engine.begin() as conn:
        fam = conn.execute(select(families).where(families.c.invite_code == invite_code)).first()
        if not fam:
            raise ValueError('Код приглашения не найден')
        target_family_id = fam._mapping['id']
        old_family_id = current_user.get('family_id')
        if old_family_id == target_family_id:
            return True
        # Если пользователь уже вел учет в своей семье и там есть операции, запрещаем тихий перенос.
        tx_count = conn.execute(select(func.count()).select_from(transactions).where(transactions.c.user_id == current_user['id'])).scalar() or 0
        if tx_count:
            raise ValueError('У пользователя уже есть операции. Для переноса семьи нужен отдельный безопасный сценарий.')
        conn.execute(update(users).where(users.c.id == current_user['id']).values(family_id=target_family_id, role=role))
        s = conn.execute(select(notification_settings).where(notification_settings.c.user_id == current_user['id'])).first()
        if not s:
            conn.execute(notification_settings.insert().values(family_id=target_family_id, user_id=current_user['id'], daily_enabled=1, budget_alert_enabled=1, scheduled_payment_enabled=1, created_at=_now()))
        else:
            conn.execute(update(notification_settings).where(notification_settings.c.user_id == current_user['id']).values(family_id=target_family_id))
        # Старую пустую семью можно оставить; она не мешает и не содержит финансовых данных.
        return True


def get_wallets(family_id: int):
    with engine.begin() as conn:
        return _rows(conn.execute(select(wallets).where(wallets.c.family_id == family_id).order_by(wallets.c.id)))

def get_categories(family_id: int, tx_type: str):
    with engine.begin() as conn:
        parent = categories.alias('parent')
        rows = conn.execute(select(
            categories.c.id, categories.c.family_id, categories.c.name, categories.c.type,
            categories.c.parent_id, categories.c.created_at, parent.c.name.label('parent_name')
        ).select_from(categories.outerjoin(parent, parent.c.id == categories.c.parent_id))
         .where(and_(categories.c.family_id == family_id, categories.c.type == tx_type))
         .order_by(categories.c.parent_id.is_not(None), categories.c.parent_id, categories.c.id)).all()
    data = _rows(rows)
    by_id = {r['id']: r for r in data}
    for r in data:
        r['is_subcategory'] = bool(r.get('parent_id'))
        r['display_name'] = (f"{r.get('parent_name')} / {r.get('name')}" if r.get('parent_name') else r.get('name'))
        r['subcategories'] = []
    for r in data:
        if r.get('parent_id') in by_id:
            by_id[r['parent_id']]['subcategories'].append(r)
    return data

def get_rates(family_id: int):
    with engine.begin() as conn:
        return _rows(conn.execute(select(exchange_rates).where(exchange_rates.c.family_id == family_id).order_by(exchange_rates.c.currency)))



def family_owns_wallet(family_id: int, wallet_id: int):
    with engine.begin() as conn:
        return conn.execute(select(wallets.c.id).where(and_(wallets.c.id == wallet_id, wallets.c.family_id == family_id))).first() is not None

def family_owns_category(family_id: int, category_id: int, tx_type=None):
    cond = [categories.c.id == category_id, categories.c.family_id == family_id]
    if tx_type:
        cond.append(categories.c.type == tx_type)
    with engine.begin() as conn:
        return conn.execute(select(categories.c.id).where(and_(*cond))).first() is not None

def get_category_id_by_name(family_id: int, name: str, tx_type: str):
    with engine.begin() as conn:
        r = conn.execute(select(categories.c.id).where(and_(categories.c.family_id == family_id, categories.c.name == name, categories.c.type == tx_type))).first()
    if not r:
        raise ValueError(f'Категория {name} не найдена')
    return int(r._mapping['id'])

def _get_wallet(conn, family_id: int, wallet_id: int):
    w = conn.execute(select(wallets).where(and_(wallets.c.id == wallet_id, wallets.c.family_id == family_id))).first()
    if not w:
        raise ValueError('Кошелек не найден')
    return w._mapping

def _insert_transaction(conn, user: dict, tx_type: str, amount: Decimal, currency: str, wallet_id: int, category_id: int | None, comment='', transfer_id: int | None = None):
    family_id = int(user['family_id'])
    rate = get_rate(family_id, currency)
    amount_base = (amount * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return conn.execute(transactions.insert().values(
        family_id=family_id, user_id=user['id'], type=tx_type, amount=amount, currency=currency,
        amount_base=amount_base, wallet_id=wallet_id, category_id=category_id, transfer_id=transfer_id,
        comment=_clean_text(comment), created_at=_now()
    )).inserted_primary_key[0]






def get_summary(family_id: int):
    with engine.begin() as conn:
        inc = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(and_(transactions.c.family_id == family_id, transactions.c.type == 'income'))).scalar() or 0
        exp = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(and_(transactions.c.family_id == family_id, transactions.c.type == 'expense'))).scalar() or 0
        wallet_base = conn.execute(select(func.coalesce(func.sum(wallets.c.balance * exchange_rates.c.rate_to_base), 0)).select_from(wallets.join(exchange_rates, and_(exchange_rates.c.family_id == wallets.c.family_id, exchange_rates.c.currency == wallets.c.currency))).where(wallets.c.family_id == family_id)).scalar() or 0
    debt_left = sum(float(d['left_base']) for d in get_debts(family_id))
    return {'income': round(float(inc), 2), 'expense': round(float(exp), 2), 'balance': round(float(wallet_base), 2), 'debt_left': round(debt_left, 2), 'base_currency': BASE_CURRENCY}

def _month_range(ym=None):
    ym = validate_month(ym)
    y, m = map(int, ym.split('-'))
    start = datetime(y, m, 1)
    end = datetime(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return ym, start, end

def get_month_summary(family_id: int, ym=None):
    ym, start, end = _month_range(ym)
    with engine.begin() as conn:
        rows = conn.execute(select(transactions.c.type, func.coalesce(func.sum(transactions.c.amount_base), 0).label('s')).where(and_(transactions.c.family_id == family_id, transactions.c.created_at >= start, transactions.c.created_at < end)).group_by(transactions.c.type)).all()
    sums = {r._mapping['type']: float(r._mapping['s'] or 0) for r in rows}
    income = sums.get('income', 0)
    expense = sums.get('expense', 0)
    debt_cat = None
    try:
        debt_cat = get_category_id_by_name(family_id, 'Долги', 'expense')
    except Exception:
        pass
    debt_paid = 0
    if debt_cat:
        with engine.begin() as conn:
            debt_paid = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(and_(transactions.c.family_id == family_id, transactions.c.category_id == debt_cat, transactions.c.created_at >= start, transactions.c.created_at < end))).scalar() or 0
    return {'month': ym, 'income': round(income, 2), 'expense': round(expense, 2), 'balance': round(income - expense, 2), 'debt_paid': round(float(debt_paid), 2)}

def get_expense_by_categories(family_id: int, ym=None, date_from=None, date_to=None):
    label, start, end = _period_range(ym, date_from, date_to)
    with engine.begin() as conn:
        parent = categories.alias('parent')
        rows = conn.execute(select(
            categories.c.id.label('category_id'), categories.c.name.label('category_name'),
            categories.c.parent_id, parent.c.name.label('parent_name'),
            func.coalesce(func.sum(transactions.c.amount_base), 0).label('amount')
        ).select_from(transactions.join(categories, categories.c.id == transactions.c.category_id).outerjoin(parent, parent.c.id == categories.c.parent_id))
         .where(and_(transactions.c.family_id == family_id, transactions.c.type == 'expense', transactions.c.created_at >= start, transactions.c.created_at < end))
         .group_by(categories.c.id, categories.c.name, categories.c.parent_id, parent.c.name)
         .order_by(text('amount DESC'))).all()
    total = sum(float(r._mapping['amount'] or 0) for r in rows)
    result = []
    for r in rows:
        m = r._mapping
        name = f"{m['parent_name']} / {m['category_name']}" if m.get('parent_name') else m['category_name']
        result.append({'category_id': m['category_id'], 'category_name': name, 'amount': round(float(m['amount'] or 0), 2), 'percent': round(float(m['amount'] or 0) / total * 100, 1) if total else 0})
    return result

def get_daily_chart(family_id: int, ym=None, date_from=None, date_to=None):
    label, start, end = _period_range(ym, date_from, date_to)
    days = {}
    cur = start
    while cur < end and cur.date() <= date.today():
        days[cur.strftime('%d')] = {'income': 0, 'expense': 0}
        cur += timedelta(days=1)
    with engine.begin() as conn:
        rows = conn.execute(select(transactions.c.type, transactions.c.amount_base, transactions.c.created_at).where(and_(transactions.c.family_id == family_id, transactions.c.type.in_(['income', 'expense']), transactions.c.created_at >= start, transactions.c.created_at < end))).all()
    for r in rows:
        key = r._mapping['created_at'].strftime('%d')
        if key in days:
            days[key][r._mapping['type']] += float(r._mapping['amount_base'] or 0)
    return {'labels': list(days.keys()), 'income': [round(v['income'], 2) for v in days.values()], 'expense': [round(v['expense'], 2) for v in days.values()]}

def get_recent_transactions(family_id: int, limit=10):
    with engine.begin() as conn:
        q = select(transactions, wallets.c.name.label('wallet_name'), categories.c.name.label('category_name'), users.c.full_name.label('user_name')).select_from(transactions.outerjoin(wallets, wallets.c.id == transactions.c.wallet_id).outerjoin(categories, categories.c.id == transactions.c.category_id).outerjoin(users, users.c.id == transactions.c.user_id)).where(transactions.c.family_id == family_id).order_by(transactions.c.id.desc()).limit(limit)
        return _rows(conn.execute(q))


def get_debts(family_id: int):
    with engine.begin() as conn:
        rows = conn.execute(select(debts).where(debts.c.family_id == family_id).order_by(debts.c.id.desc())).all()
    result = []
    for r in rows:
        d = dict(r._mapping)
        d['left_amount'] = round(float(d['total_amount'] or 0) - float(d['paid_amount'] or 0), 2)
        d['left_base'] = round(float(d['total_base'] or 0) - float(d['paid_base'] or 0), 2)
        result.append(d)
    return result


def add_goal(user: dict, name: str, target_amount: float, currency: str, deadline=''):
    require_permission(user, 'manage_goals')
    name = _clean_text(name, 160)
    if not name:
        raise ValueError('Введите название цели')
    target_amount = validate_amount(target_amount, 'Целевая сумма')
    currency = validate_currency(currency)
    deadline = _clean_text(deadline, 20)
    with engine.begin() as conn:
        return conn.execute(goals.insert().values(family_id=user['family_id'], name=name, target_amount=target_amount, current_amount=0, currency=currency, deadline=deadline, created_at=_now())).inserted_primary_key[0]


def get_goals(family_id: int):
    with engine.begin() as conn:
        return _rows(conn.execute(select(goals).where(goals.c.family_id == family_id).order_by(goals.c.id.desc())))


def get_budgets(family_id: int, ym=None):
    ym = validate_month(ym)
    cats = {c['category_name']: c for c in get_expense_by_categories(family_id, ym)}
    with engine.begin() as conn:
        rows = conn.execute(select(budgets, categories.c.name.label('category_name')).select_from(budgets.join(categories, categories.c.id == budgets.c.category_id)).where(and_(budgets.c.family_id == family_id, budgets.c.month == ym))).all()
    out = []
    for r in rows:
        b = dict(r._mapping)
        spent = float(cats.get(b['category_name'], {}).get('amount', 0))
        b['spent_base'] = round(spent, 2)
        b['left_base'] = round(float(b['limit_base']) - spent, 2)
        b['percent'] = round(spent / float(b['limit_base']) * 100, 1) if b['limit_base'] else 0
        out.append(b)
    return out



def validate_date(value: str | None, field='Дата'):
    if not value:
        return None
    value = str(value).strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError(f'{field} должна быть в формате YYYY-MM-DD')
    return datetime.strptime(value, '%Y-%m-%d')

def _period_range(ym=None, date_from=None, date_to=None):
    """Возвращает период [start, end). Если заданы даты, они важнее месяца."""
    if date_from or date_to:
        start = validate_date(date_from, 'Дата с') or datetime(date.today().year, date.today().month, 1)
        end_dt = validate_date(date_to, 'Дата по')
        if end_dt:
            end = end_dt + timedelta(days=1)
        else:
            end = _now() + timedelta(days=1)
        if start >= end:
            raise ValueError('Дата начала должна быть раньше даты окончания')
        label = f'{start.date()} — {(end - timedelta(days=1)).date()}'
        return label, start, end
    return _month_range(ym)

def get_period_summary(family_id: int, ym=None, date_from=None, date_to=None):
    label, start, end = _period_range(ym, date_from, date_to)
    with engine.begin() as conn:
        rows = conn.execute(select(transactions.c.type, func.coalesce(func.sum(transactions.c.amount_base), 0).label('s')).where(and_(transactions.c.family_id == family_id, transactions.c.created_at >= start, transactions.c.created_at < end)).group_by(transactions.c.type)).all()
    sums = {r._mapping['type']: float(r._mapping['s'] or 0) for r in rows}
    income = sums.get('income', 0)
    expense = sums.get('expense', 0)
    return {'period': label, 'income': round(income, 2), 'expense': round(expense, 2), 'balance': round(income - expense, 2)}

def get_wallet_report(family_id: int):
    """Отчет по кошелькам: реальный остаток и эквивалент в базовой валюте."""
    with engine.begin() as conn:
        q = select(
            wallets.c.id, wallets.c.name, wallets.c.currency, wallets.c.balance,
            exchange_rates.c.rate_to_base,
            (wallets.c.balance * exchange_rates.c.rate_to_base).label('balance_base')
        ).select_from(wallets.join(exchange_rates, and_(exchange_rates.c.family_id == wallets.c.family_id, exchange_rates.c.currency == wallets.c.currency))).where(wallets.c.family_id == family_id).order_by(wallets.c.id)
        rows = conn.execute(q).all()
    out = []
    for r in rows:
        item = dict(r._mapping)
        item['balance'] = round(float(item.get('balance') or 0), 2)
        item['rate_to_base'] = round(float(item.get('rate_to_base') or 0), 6)
        item['balance_base'] = round(float(item.get('balance_base') or 0), 2)
        out.append(item)
    return out

def get_member_report(family_id: int, ym=None, date_from=None, date_to=None):
    """Сколько доходов/расходов внес каждый член семьи за выбранный период."""
    label, start, end = _period_range(ym, date_from, date_to)
    with engine.begin() as conn:
        rows = conn.execute(select(
            users.c.id.label('user_id'), users.c.full_name, users.c.role,
            transactions.c.type,
            func.coalesce(func.sum(transactions.c.amount_base), 0).label('amount'),
            func.count(transactions.c.id).label('count')
        ).select_from(transactions.join(users, users.c.id == transactions.c.user_id)).where(and_(transactions.c.family_id == family_id, transactions.c.created_at >= start, transactions.c.created_at < end, transactions.c.type.in_(['income','expense']))).group_by(users.c.id, users.c.full_name, users.c.role, transactions.c.type)).all()
    by_user = {}
    for r in rows:
        m = r._mapping
        item = by_user.setdefault(m['user_id'], {'user_id': m['user_id'], 'full_name': m['full_name'], 'role': m['role'], 'income': 0, 'expense': 0, 'count': 0, 'balance': 0})
        item[m['type']] = round(float(m['amount'] or 0), 2)
        item['count'] += int(m['count'] or 0)
    for item in by_user.values():
        item['balance'] = round(item['income'] - item['expense'], 2)
    return sorted(by_user.values(), key=lambda x: x['expense'], reverse=True)

def get_currency_report(family_id: int, ym=None, date_from=None, date_to=None):
    """Доходы/расходы по валютам + остатки кошельков по валютам."""
    label, start, end = _period_range(ym, date_from, date_to)
    with engine.begin() as conn:
        tx_rows = conn.execute(select(
            transactions.c.currency, transactions.c.type,
            func.coalesce(func.sum(transactions.c.amount), 0).label('amount'),
            func.coalesce(func.sum(transactions.c.amount_base), 0).label('amount_base')
        ).where(and_(transactions.c.family_id == family_id, transactions.c.created_at >= start, transactions.c.created_at < end, transactions.c.type.in_(['income','expense']))).group_by(transactions.c.currency, transactions.c.type)).all()
        wallet_rows = conn.execute(select(wallets.c.currency, func.coalesce(func.sum(wallets.c.balance), 0).label('wallet_balance')).where(wallets.c.family_id == family_id).group_by(wallets.c.currency)).all()
    data = {c: {'currency': c, 'income': 0, 'expense': 0, 'income_base': 0, 'expense_base': 0, 'wallet_balance': 0} for c in ALLOWED_CURRENCIES}
    for r in tx_rows:
        m = r._mapping; cur = m['currency']; typ = m['type']
        item = data.setdefault(cur, {'currency': cur, 'income': 0, 'expense': 0, 'income_base': 0, 'expense_base': 0, 'wallet_balance': 0})
        item[typ] = round(float(m['amount'] or 0), 2)
        item[f'{typ}_base'] = round(float(m['amount_base'] or 0), 2)
    for r in wallet_rows:
        m = r._mapping; cur = m['currency']
        item = data.setdefault(cur, {'currency': cur, 'income': 0, 'expense': 0, 'income_base': 0, 'expense_base': 0, 'wallet_balance': 0})
        item['wallet_balance'] = round(float(m['wallet_balance'] or 0), 2)
    return [v for v in data.values() if v['income'] or v['expense'] or v['wallet_balance']]

def get_transactions_for_export(family_id: int, ym=None, date_from=None, date_to=None):
    label, start, end = _period_range(ym, date_from, date_to)
    with engine.begin() as conn:
        q = select(transactions, wallets.c.name.label('wallet_name'), categories.c.name.label('category_name'), users.c.full_name.label('user_name')).select_from(transactions.outerjoin(wallets, wallets.c.id == transactions.c.wallet_id).outerjoin(categories, categories.c.id == transactions.c.category_id).outerjoin(users, users.c.id == transactions.c.user_id)).where(and_(transactions.c.family_id == family_id, transactions.c.created_at >= start, transactions.c.created_at < end)).order_by(transactions.c.created_at.desc(), transactions.c.id.desc())
        return _rows(conn.execute(q))

def get_all_transactions_for_export(family_id: int):
    return get_recent_transactions(family_id, 10000)

def get_users_for_reminders():
    with engine.begin() as conn:
        q = select(users.c.telegram_id, users.c.family_id, users.c.full_name).select_from(users.join(notification_settings, notification_settings.c.user_id == users.c.id)).where(notification_settings.c.daily_enabled == 1)
        return _rows(conn.execute(q))

# --- Level 3.3 admin/production helpers ---


def get_admin_families(limit: int = 100):
    limit = max(1, min(int(limit or 100), 500))
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                families.c.id,
                families.c.name,
                families.c.invite_code,
                families.c.base_currency,
                families.c.created_at,
                func.count(users.c.id).label('members_count'),
            )
            .select_from(families.outerjoin(users, users.c.family_id == families.c.id))
            .group_by(families.c.id)
            .order_by(families.c.id.desc())
            .limit(limit)
        ).fetchall()
        return _rows(rows)




# --- Level 3.5: management, filters, admin improvements ---




def get_transactions_filtered(family_id: int, *, q: str = '', tx_type: str = '', wallet_id=None, category_id=None, user_id=None, currency: str = '', date_from=None, date_to=None, limit=100):
    limit = max(1, min(int(limit or 100), 500))
    cond = [transactions.c.family_id == family_id]
    if tx_type:
        if tx_type not in {'income','expense','transfer_in','transfer_out'}:
            raise ValueError('Неверный тип операции')
        cond.append(transactions.c.type == tx_type)
    if wallet_id:
        cond.append(transactions.c.wallet_id == int(wallet_id))
    if category_id:
        cond.append(transactions.c.category_id == int(category_id))
    if user_id:
        cond.append(transactions.c.user_id == int(user_id))
    if currency:
        cond.append(transactions.c.currency == validate_currency(currency))
    if date_from:
        cond.append(transactions.c.created_at >= validate_date(date_from, 'Дата с'))
    if date_to:
        cond.append(transactions.c.created_at < validate_date(date_to, 'Дата по') + timedelta(days=1))
    query_text = _clean_text(q, 80)
    if query_text:
        cond.append(transactions.c.comment.ilike(f'%{query_text}%'))
    with engine.begin() as conn:
        stmt = select(
            transactions,
            wallets.c.name.label('wallet_name'),
            categories.c.name.label('category_name'),
            users.c.full_name.label('user_name')
        ).select_from(
            transactions.outerjoin(wallets, wallets.c.id == transactions.c.wallet_id)
            .outerjoin(categories, categories.c.id == transactions.c.category_id)
            .outerjoin(users, users.c.id == transactions.c.user_id)
        ).where(and_(*cond)).order_by(transactions.c.created_at.desc(), transactions.c.id.desc()).limit(limit)
        return _rows(conn.execute(stmt))


def admin_set_user_role(user_id: int, role: str):
    role = _clean_text(role, 24)
    if role not in ALLOWED_ROLES:
        raise ValueError('Неверная роль')
    with engine.begin() as conn:
        row = conn.execute(select(users).where(users.c.id == int(user_id))).first()
        if not row:
            raise ValueError('Пользователь не найден')
        conn.execute(update(users).where(users.c.id == int(user_id)).values(role=role))
        return True



def get_rate(family_id: int, currency: str) -> Decimal:  # override: always Decimal
    currency = validate_currency(currency)
    with engine.begin() as conn:
        r = conn.execute(select(exchange_rates.c.rate_to_base).where(and_(exchange_rates.c.family_id == family_id, exchange_rates.c.currency == currency))).first()
    if not r:
        raise ValueError(f'Нет курса для валюты {currency}')
    return _rate(r._mapping['rate_to_base'])

def _log(conn, user: dict | None, action: str, entity_type: str, entity_id: int | None = None, details: str = ''):
    family_id = int((user or {}).get('family_id') or 0)
    if not family_id:
        return
    conn.execute(audit_logs.insert().values(
        family_id=family_id,
        user_id=(user or {}).get('id'),
        action=_clean_text(action, 64),
        entity_type=_clean_text(entity_type, 64),
        entity_id=entity_id,
        details=_clean_text(details, 1000),
        created_at=_now(),
    ))

def get_audit_logs(family_id: int, limit: int = 100):
    limit = max(1, min(int(limit or 100), 500))
    with engine.begin() as conn:
        rows = conn.execute(select(
            audit_logs.c.id, audit_logs.c.action, audit_logs.c.entity_type, audit_logs.c.entity_id,
            audit_logs.c.details, audit_logs.c.created_at, users.c.full_name.label('user_name')
        ).select_from(audit_logs.outerjoin(users, users.c.id == audit_logs.c.user_id))
         .where(audit_logs.c.family_id == family_id).order_by(audit_logs.c.id.desc()).limit(limit)).all()
    return _rows(rows)

def _base_safe_migrations():
    pass

_prev_safe_migrations_l35 = _base_safe_migrations

def set_rate(user: dict, currency: str, rate_to_base: float):
    require_permission(user, 'manage_rates')
    family_id = int(user['family_id'])
    currency = validate_currency(currency)
    rate_to_base = _rate(rate_to_base, 'Курс')
    if currency == BASE_CURRENCY and rate_to_base != Decimal('1.000000'):
        raise ValueError(f'Курс базовой валюты {BASE_CURRENCY} должен быть 1')
    with engine.begin() as conn:
        old = conn.execute(select(exchange_rates).where(and_(exchange_rates.c.family_id == family_id, exchange_rates.c.currency == currency))).first()
        if old:
            conn.execute(update(exchange_rates).where(exchange_rates.c.id == old._mapping['id']).values(rate_to_base=rate_to_base, updated_at=_now()))
            rid = old._mapping['id']
        else:
            rid = conn.execute(exchange_rates.insert().values(family_id=family_id, currency=currency, rate_to_base=rate_to_base, updated_at=_now())).inserted_primary_key[0]
        _log(conn, user, 'update_rate', 'exchange_rate', int(rid), f'{currency}={rate_to_base}')

def _amount_base(family_id: int, amount: Decimal, currency: str) -> Decimal:
    return (amount * get_rate(family_id, currency)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def add_transaction(user: dict, tx_type: str, amount: float, currency: str, wallet_id: int, category_id: int, comment=''):
    require_permission(user, 'add_transaction')
    family_id = int(user['family_id'])
    tx_type = _clean_text(tx_type, 16)
    if tx_type not in ALLOWED_TX_TYPES:
        raise ValueError('Неверный тип операции')
    amount = validate_amount(amount)
    currency = validate_currency(currency)
    comment = _clean_text(comment)
    if not family_owns_category(family_id, category_id, tx_type):
        raise ValueError('Категория не найдена')
    with engine.begin() as conn:
        w = _get_wallet(conn, family_id, wallet_id)
        if w['currency'] != currency:
            raise ValueError(f'Валюта операции должна совпадать с валютой кошелька: {w["currency"]}')
        old_balance = _d(w['balance'])
        if tx_type == 'expense' and old_balance < amount:
            raise ValueError('Недостаточно средств в кошельке')
        tx_id = conn.execute(transactions.insert().values(
            family_id=family_id, user_id=user['id'], type=tx_type, amount=amount, currency=currency,
            amount_base=_amount_base(family_id, amount, currency), wallet_id=wallet_id, category_id=category_id,
            transfer_id=None, comment=comment, created_at=_now()
        )).inserted_primary_key[0]
        delta = amount if tx_type == 'income' else -amount
        conn.execute(update(wallets).where(wallets.c.id == wallet_id).values(balance=old_balance + delta))
        _log(conn, user, 'create', 'transaction', int(tx_id), f'{tx_type} {amount} {currency}')
        return int(tx_id)



def transfer_between_wallets(user: dict, from_wallet_id: int, to_wallet_id: int, amount_from: float, amount_to: float | None = None, comment=''):
    require_permission(user, 'transfer')
    family_id = int(user['family_id'])
    amount_from = validate_amount(amount_from, 'Сумма списания')
    comment = _clean_text(comment)
    with engine.begin() as conn:
        src = _get_wallet(conn, family_id, from_wallet_id)
        dst = _get_wallet(conn, family_id, to_wallet_id)
        if src['id'] == dst['id']:
            raise ValueError('Выберите два разных кошелька')
        src_balance = _d(src['balance'])
        if src_balance < amount_from:
            raise ValueError('Недостаточно средств в исходном кошельке')
        src_rate = get_rate(family_id, src['currency'])
        dst_rate = get_rate(family_id, dst['currency'])
        amount_to = (amount_from * src_rate / dst_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if amount_to in (None, '', 0) else validate_amount(amount_to, 'Сумма зачисления')
        base = (amount_from * src_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        now = _now()
        transfer_id = conn.execute(transfers.insert().values(
            family_id=family_id, user_id=user['id'], from_wallet_id=from_wallet_id, to_wallet_id=to_wallet_id,
            amount_from=amount_from, currency_from=src['currency'], amount_to=amount_to, currency_to=dst['currency'],
            amount_base=base, comment=comment, created_at=now
        )).inserted_primary_key[0]
        conn.execute(transactions.insert(), [
            {'family_id': family_id, 'user_id': user['id'], 'type': 'transfer_out', 'amount': amount_from, 'currency': src['currency'], 'amount_base': base, 'wallet_id': from_wallet_id, 'category_id': None, 'transfer_id': transfer_id, 'comment': comment or f'Перевод в {dst["name"]}', 'created_at': now},
            {'family_id': family_id, 'user_id': user['id'], 'type': 'transfer_in', 'amount': amount_to, 'currency': dst['currency'], 'amount_base': (amount_to * dst_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'wallet_id': to_wallet_id, 'category_id': None, 'transfer_id': transfer_id, 'comment': comment or f'Перевод из {src["name"]}', 'created_at': now},
        ])
        conn.execute(update(wallets).where(wallets.c.id == from_wallet_id).values(balance=src_balance - amount_from))
        conn.execute(update(wallets).where(wallets.c.id == to_wallet_id).values(balance=_d(dst['balance']) + amount_to))
        _log(conn, user, 'create', 'transfer', int(transfer_id), f'{amount_from} {src["currency"]} -> {amount_to} {dst["currency"]}')
        return int(transfer_id)

def delete_transfer(user: dict, transfer_id: int):
    require_permission(user, 'transfer')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        tr = conn.execute(select(transfers).where(and_(transfers.c.id == transfer_id, transfers.c.family_id == family_id))).first()
        if not tr:
            raise ValueError('Перевод не найден')
        t = tr._mapping
        src = _get_wallet(conn, family_id, int(t['from_wallet_id']))
        dst = _get_wallet(conn, family_id, int(t['to_wallet_id']))
        amount_to = _d(t['amount_to']); amount_from = _d(t['amount_from'])
        if _d(dst['balance']) < amount_to:
            raise ValueError('Нельзя удалить перевод: в кошельке-получателе уже недостаточно средств для отката')
        conn.execute(update(wallets).where(wallets.c.id == src['id']).values(balance=_d(src['balance']) + amount_from))
        conn.execute(update(wallets).where(wallets.c.id == dst['id']).values(balance=_d(dst['balance']) - amount_to))
        conn.execute(delete(transactions).where(transactions.c.transfer_id == transfer_id))
        conn.execute(delete(transfers).where(transfers.c.id == transfer_id))
        _log(conn, user, 'delete', 'transfer', int(transfer_id), f'rollback {amount_from}/{amount_to}')
        return True

def add_debt(user: dict, name: str, total_amount: float, currency: str, comment=''):
    require_permission(user, 'manage_debt')
    family_id = int(user['family_id'])
    name = _clean_text(name, 160)
    if not name:
        raise ValueError('Введите название долга')
    total_amount = validate_amount(total_amount)
    currency = validate_currency(currency)
    total_base = _amount_base(family_id, total_amount, currency)
    with engine.begin() as conn:
        debt_id = conn.execute(debts.insert().values(family_id=family_id, user_id=user['id'], name=name, total_amount=total_amount, paid_amount=Decimal('0.00'), currency=currency, total_base=total_base, paid_base=Decimal('0.00'), comment=_clean_text(comment), created_at=_now())).inserted_primary_key[0]
        _log(conn, user, 'create', 'debt', int(debt_id), f'{name}: {total_amount} {currency}')
        return int(debt_id)



def set_budget(user: dict, category_id: int, month: str, limit_amount: float, currency: str):
    require_permission(user, 'manage_budget')
    family_id = int(user['family_id'])
    month = validate_month(month)
    limit_amount = validate_amount(limit_amount, 'Лимит')
    currency = validate_currency(currency)
    if not family_owns_category(family_id, category_id, 'expense'):
        raise ValueError('Категория не найдена')
    with engine.begin() as conn:
        old = conn.execute(select(budgets).where(and_(budgets.c.family_id == family_id, budgets.c.category_id == category_id, budgets.c.month == month))).first()
        vals = {'limit_amount': limit_amount, 'currency': currency, 'limit_base': _amount_base(family_id, limit_amount, currency)}
        if old:
            conn.execute(update(budgets).where(budgets.c.id == old._mapping['id']).values(**vals))
            bid = old._mapping['id']
        else:
            bid = conn.execute(budgets.insert().values(family_id=family_id, category_id=category_id, month=month, created_at=_now(), **vals)).inserted_primary_key[0]
        _log(conn, user, 'upsert', 'budget', int(bid), f'category={category_id}; month={month}; limit={limit_amount} {currency}')
    return {'id': int(bid), 'category_id': int(category_id), 'month': month, 'limit_amount': float(limit_amount), 'currency': currency, 'limit_base': float(vals['limit_base'])}

def get_budget_alerts(family_id: int, ym=None):
    alerts = []
    for b in get_budgets(family_id, ym):
        try:
            if float(b.get('percent') or 0) >= 100:
                alerts.append(f'⚠️ Превышен лимит: {b.get("category_name")} — {b.get("percent")}% ({b.get("spent_base")} из {b.get("limit_base")})')
        except Exception:
            continue
    return alerts

def add_wallet(user: dict, name: str, currency: str = None, initial_balance: float = 0, include_in_free_money: bool = True):
    require_permission(user, 'manage_wallets')
    name = _clean_text(name, 120)
    if not name:
        raise ValueError('Название кошелька обязательно')
    currency = validate_currency(currency or BASE_CURRENCY)
    initial_balance_dec = Decimal(str(initial_balance or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if initial_balance_dec < 0:
        raise ValueError('Начальный баланс не может быть отрицательным')
    with engine.begin() as conn:
        exists = conn.execute(select(wallets.c.id).where(and_(wallets.c.family_id == user['family_id'], wallets.c.name == name))).first()
        if exists:
            raise ValueError('Кошелек с таким названием уже существует')
        wallet_id = conn.execute(wallets.insert().values(family_id=user['family_id'], name=name, currency=currency, balance=initial_balance_dec, include_in_free_money=1 if include_in_free_money else 0, created_at=_now())).inserted_primary_key[0]
        if initial_balance_dec > 0:
            cat = conn.execute(select(categories.c.id).where(and_(categories.c.family_id == user['family_id'], categories.c.type == 'income')).order_by(categories.c.id)).first()
            cat_id = cat._mapping['id'] if cat else conn.execute(categories.insert().values(family_id=user['family_id'], name='Начальный баланс', type='income', created_at=_now())).inserted_primary_key[0]
            conn.execute(transactions.insert().values(family_id=user['family_id'], user_id=user['id'], type='income', amount=initial_balance_dec, currency=currency, amount_base=_amount_base(user['family_id'], initial_balance_dec, currency), wallet_id=wallet_id, category_id=cat_id, transfer_id=None, comment='Начальный баланс', created_at=_now()))
        _log(conn, user, 'create', 'wallet', int(wallet_id), f'{name} {currency}')
        return int(wallet_id)

def update_wallet(user: dict, wallet_id: int, name: str, include_in_free_money=None):
    require_permission(user, 'manage_wallets')
    name = _clean_text(name, 120)
    if not name:
        raise ValueError('Название кошелька обязательно')
    vals = {'name': name}
    if include_in_free_money is not None:
        vals['include_in_free_money'] = 1 if bool(include_in_free_money) else 0
    with engine.begin() as conn:
        w = _get_wallet(conn, int(user['family_id']), int(wallet_id))
        conn.execute(update(wallets).where(wallets.c.id == int(wallet_id)).values(**vals))
        _log(conn, user, 'edit', 'wallet', int(wallet_id), f'{w["name"]} -> {name}; include_in_free_money={vals.get("include_in_free_money", w.get("include_in_free_money", 1))}')
        return True

def delete_wallet(user: dict, wallet_id: int):
    require_permission(user, 'manage_wallets')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        w = _get_wallet(conn, family_id, int(wallet_id))
        tx_count = conn.execute(select(func.count()).select_from(transactions).where(transactions.c.wallet_id == int(wallet_id))).scalar() or 0
        if tx_count:
            raise ValueError('Нельзя удалить кошелек, по которому уже есть операции. Переименуйте его или создайте новый.')
        if _d(w['balance']) != Decimal('0.00'):
            raise ValueError('Нельзя удалить кошелек с ненулевым балансом')
        conn.execute(delete(wallets).where(wallets.c.id == int(wallet_id)))
        _log(conn, user, 'delete', 'wallet', int(wallet_id), w['name'])
        return True

def add_category(user: dict, name: str, tx_type: str, parent_id: int | None = None):
    require_permission(user, 'manage_categories')
    name = _clean_text(name, 120)
    tx_type = str(tx_type or '').strip()
    parent_id = int(parent_id) if parent_id else None
    if not name:
        raise ValueError('Название категории обязательно')
    if tx_type not in ALLOWED_TX_TYPES:
        raise ValueError('Тип категории должен быть income или expense')
    with engine.begin() as conn:
        if parent_id:
            parent = conn.execute(select(categories).where(and_(categories.c.id == parent_id, categories.c.family_id == user['family_id'], categories.c.type == tx_type))).first()
            if not parent:
                raise ValueError('Родительская категория не найдена')
            if parent._mapping.get('parent_id'):
                raise ValueError('Подкатегорию можно создать только внутри основной категории')
        exists = conn.execute(select(categories.c.id).where(and_(categories.c.family_id == user['family_id'], categories.c.name == name, categories.c.type == tx_type, categories.c.parent_id.is_(parent_id) if parent_id is None else categories.c.parent_id == parent_id))).first()
        if exists:
            raise ValueError('Категория с таким названием уже существует')
        cid = conn.execute(categories.insert().values(family_id=user['family_id'], name=name, type=tx_type, parent_id=parent_id, created_at=_now())).inserted_primary_key[0]
        _log(conn, user, 'create', 'category', int(cid), f'{name} {tx_type}; parent={parent_id or ""}')
        return int(cid)

def update_category(user: dict, category_id: int, name: str):
    require_permission(user, 'manage_categories')
    family_id = int(user['family_id'])
    name = _clean_text(name, 120)
    if not name:
        raise ValueError('Название категории обязательно')
    with engine.begin() as conn:
        c = conn.execute(select(categories).where(and_(categories.c.id == int(category_id), categories.c.family_id == family_id))).first()
        if not c:
            raise ValueError('Категория не найдена')
        conn.execute(update(categories).where(categories.c.id == int(category_id)).values(name=name))
        _log(conn, user, 'edit', 'category', int(category_id), f'{c._mapping["name"]} -> {name}')
        return True

def delete_category(user: dict, category_id: int):
    require_permission(user, 'manage_categories')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        c = conn.execute(select(categories).where(and_(categories.c.id == int(category_id), categories.c.family_id == family_id))).first()
        if not c:
            raise ValueError('Категория не найдена')
        child_count = conn.execute(select(func.count()).select_from(categories).where(categories.c.parent_id == int(category_id))).scalar() or 0
        if child_count:
            raise ValueError('Нельзя удалить категорию, у которой есть подкатегории')
        tx_count = conn.execute(select(func.count()).select_from(transactions).where(transactions.c.category_id == int(category_id))).scalar() or 0
        if tx_count:
            raise ValueError('Нельзя удалить категорию, по которой уже есть операции. Переименуйте ее.')
        conn.execute(delete(categories).where(categories.c.id == int(category_id)))
        _log(conn, user, 'delete', 'category', int(category_id), c._mapping['name'])
        return True

# --- Level 3.7: financial integrity and rollback for linked operations ---
# Денежная целостность: платежи по долгам и пополнения целей теперь связаны с операциями.
# При удалении связанной операции откатываются и кошелек, и связанная сущность.

_prev_safe_migrations_l36 = _prev_safe_migrations_l35


def get_debt_payments(family_id: int, debt_id: int | None = None):
    with engine.begin() as conn:
        cond = [debt_payments.c.family_id == family_id]
        if debt_id:
            cond.append(debt_payments.c.debt_id == int(debt_id))
        rows = conn.execute(select(
            debt_payments.c.id, debt_payments.c.debt_id, debt_payments.c.wallet_id,
            debt_payments.c.transaction_id, debt_payments.c.amount, debt_payments.c.currency,
            debt_payments.c.amount_base, debt_payments.c.created_at,
            debts.c.name.label('debt_name'), wallets.c.name.label('wallet_name'), users.c.full_name.label('user_name')
        ).select_from(
            debt_payments.join(debts, debts.c.id == debt_payments.c.debt_id)
                         .join(wallets, wallets.c.id == debt_payments.c.wallet_id)
                         .outerjoin(users, users.c.id == debt_payments.c.user_id)
        ).where(and_(*cond)).order_by(debt_payments.c.id.desc())).all()
    return _rows(rows)


def get_goal_contributions(family_id: int, goal_id: int | None = None):
    with engine.begin() as conn:
        cond = [goal_contributions.c.family_id == family_id]
        if goal_id:
            cond.append(goal_contributions.c.goal_id == int(goal_id))
        rows = conn.execute(select(
            goal_contributions.c.id, goal_contributions.c.goal_id, goal_contributions.c.wallet_id,
            goal_contributions.c.transaction_id, goal_contributions.c.amount, goal_contributions.c.currency,
            goal_contributions.c.created_at,
            goals.c.name.label('goal_name'), wallets.c.name.label('wallet_name'), users.c.full_name.label('user_name')
        ).select_from(
            goal_contributions.join(goals, goals.c.id == goal_contributions.c.goal_id)
                              .join(wallets, wallets.c.id == goal_contributions.c.wallet_id)
                              .outerjoin(users, users.c.id == goal_contributions.c.user_id)
        ).where(and_(*cond)).order_by(goal_contributions.c.id.desc())).all()
    return _rows(rows)


def _ensure_expense_category(conn, family_id: int, name: str) -> int:
    row = conn.execute(select(categories.c.id).where(and_(categories.c.family_id == family_id, categories.c.name == name, categories.c.type == 'expense'))).first()
    if row:
        return int(row._mapping['id'])
    return int(conn.execute(categories.insert().values(family_id=family_id, name=name, type='expense', created_at=_now())).inserted_primary_key[0])


def _rollback_plain_transaction(conn, family_id: int, tx_row):
    t = tx_row._mapping if hasattr(tx_row, '_mapping') else tx_row
    if t['type'] not in ALLOWED_TX_TYPES:
        raise ValueError('Эту операцию нельзя откатить как обычную операцию')
    w = _get_wallet(conn, family_id, int(t['wallet_id']))
    amount = _d(t['amount'])
    rollback_delta = -amount if t['type'] == 'income' else amount
    new_balance = _d(w['balance']) + rollback_delta
    if new_balance < 0:
        raise ValueError('Нельзя отменить/удалить операцию: баланс кошелька уйдет в минус')
    conn.execute(update(wallets).where(wallets.c.id == w['id']).values(balance=new_balance))


def edit_transaction(user: dict, transaction_id: int, amount: float, wallet_id: int, category_id: int, comment=''):
    """Редактирование только обычных операций. Связанные операции по долгам/целям редактировать нельзя — их нужно удалить и создать заново."""
    require_permission(user, 'add_transaction')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        linked_debt = conn.execute(select(debt_payments.c.id).where(and_(debt_payments.c.family_id == family_id, debt_payments.c.transaction_id == transaction_id))).first()
        linked_goal = conn.execute(select(goal_contributions.c.id).where(and_(goal_contributions.c.family_id == family_id, goal_contributions.c.transaction_id == transaction_id))).first()
        if linked_debt:
            raise ValueError('Платеж по долгу нельзя редактировать напрямую. Удалите платеж и создайте новый.')
        if linked_goal:
            raise ValueError('Пополнение цели нельзя редактировать напрямую. Удалите пополнение и создайте новое.')
    # вызываем реализацию 3.6 через сохраненную логику невозможно, поэтому повторяем безопасно
    new_amount = validate_amount(amount)
    with engine.begin() as conn:
        tx = conn.execute(select(transactions).where(and_(transactions.c.id == transaction_id, transactions.c.family_id == family_id))).first()
        if not tx:
            raise ValueError('Операция не найдена')
        t = tx._mapping
        if t['type'] not in ALLOWED_TX_TYPES or t.get('transfer_id'):
            raise ValueError('Эту операцию нельзя редактировать как обычную операцию')
        currency = validate_currency(t['currency'])
        if not family_owns_category(family_id, category_id, t['type']):
            raise ValueError('Категория не найдена')
        old_wallet = _get_wallet(conn, family_id, int(t['wallet_id']))
        new_wallet = _get_wallet(conn, family_id, wallet_id)
        if new_wallet['currency'] != currency:
            raise ValueError(f'Валюта нового кошелька должна быть {currency}')
        old_amount = _d(t['amount'])
        rollback_delta = -old_amount if t['type'] == 'income' else old_amount
        conn.execute(update(wallets).where(wallets.c.id == old_wallet['id']).values(balance=_d(old_wallet['balance']) + rollback_delta))
        refreshed = _get_wallet(conn, family_id, wallet_id)
        if t['type'] == 'expense' and _d(refreshed['balance']) < new_amount:
            raise ValueError('Недостаточно средств в кошельке после редактирования')
        new_delta = new_amount if t['type'] == 'income' else -new_amount
        conn.execute(update(wallets).where(wallets.c.id == wallet_id).values(balance=_d(refreshed['balance']) + new_delta))
        conn.execute(update(transactions).where(transactions.c.id == transaction_id).values(
            amount=new_amount, amount_base=_amount_base(family_id, new_amount, currency),
            wallet_id=wallet_id, category_id=category_id, comment=_clean_text(comment)
        ))
        _log(conn, user, 'edit', 'transaction', int(transaction_id), f'amount={new_amount}; wallet={wallet_id}; category={category_id}')
        return True


def delete_transaction(user: dict, transaction_id: int):
    """Удаляет операцию с полным откатом связей: кошелек + долг/цель/перевод."""
    require_permission(user, 'add_transaction')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        tx = conn.execute(select(transactions).where(and_(transactions.c.id == transaction_id, transactions.c.family_id == family_id))).first()
        if not tx:
            raise ValueError('Операция не найдена')
        t = tx._mapping
        if t.get('transfer_id'):
            transfer_id = int(t['transfer_id'])
        else:
            transfer_id = None
    if transfer_id:
        return delete_transfer(user, transfer_id)

    with engine.begin() as conn:
        tx = conn.execute(select(transactions).where(and_(transactions.c.id == transaction_id, transactions.c.family_id == family_id))).first()
        if not tx:
            raise ValueError('Операция уже удалена')
        t = tx._mapping

        debt_payment = conn.execute(select(debt_payments).where(and_(debt_payments.c.family_id == family_id, debt_payments.c.transaction_id == transaction_id))).first()
        goal_contribution = conn.execute(select(goal_contributions).where(and_(goal_contributions.c.family_id == family_id, goal_contributions.c.transaction_id == transaction_id))).first()

        # 1) откат кошелька по самой операции
        _rollback_plain_transaction(conn, family_id, t)

        # 2) откат долга, если это платеж по долгу
        if debt_payment:
            p = debt_payment._mapping
            debt = conn.execute(select(debts).where(and_(debts.c.id == p['debt_id'], debts.c.family_id == family_id))).first()
            if debt:
                d = debt._mapping
                new_paid = max(Decimal('0'), _d(d['paid_amount']) - _d(p['amount']))
                new_paid_base = max(Decimal('0'), _d(d['paid_base']) - _d(p['amount_base']))
                conn.execute(update(debts).where(debts.c.id == p['debt_id']).values(paid_amount=new_paid, paid_base=new_paid_base))
            conn.execute(delete(debt_payments).where(debt_payments.c.id == p['id']))
            _log(conn, user, 'rollback', 'debt_payment', int(p['id']), f'tx={transaction_id}; debt={p["debt_id"]}')

        # 3) откат цели, если это пополнение цели
        if goal_contribution:
            c = goal_contribution._mapping
            goal = conn.execute(select(goals).where(and_(goals.c.id == c['goal_id'], goals.c.family_id == family_id))).first()
            if goal:
                g = goal._mapping
                new_current = max(Decimal('0'), _d(g['current_amount']) - _d(c['amount']))
                conn.execute(update(goals).where(goals.c.id == c['goal_id']).values(current_amount=new_current))
            conn.execute(delete(goal_contributions).where(goal_contributions.c.id == c['id']))
            _log(conn, user, 'rollback', 'goal_contribution', int(c['id']), f'tx={transaction_id}; goal={c["goal_id"]}')

        conn.execute(delete(transactions).where(transactions.c.id == transaction_id))
        _log(conn, user, 'delete', 'transaction', int(transaction_id), 'full rollback complete')
        return True


def pay_debt(user: dict, debt_id: int, amount: float, wallet_id: int):
    """Погашение долга в одной транзакции: расход + debt_payments + обновление debt."""
    require_permission(user, 'manage_debt')
    family_id = int(user['family_id'])
    amount = validate_amount(amount)
    with engine.begin() as conn:
        debt = conn.execute(select(debts).where(and_(debts.c.id == debt_id, debts.c.family_id == family_id))).first()
        if not debt:
            raise ValueError('Долг не найден')
        d = debt._mapping
        currency = validate_currency(d['currency'])
        left = _d(d['total_amount']) - _d(d['paid_amount'])
        if left <= 0:
            raise ValueError('Долг уже погашен')
        if amount > left:
            amount = left.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        wallet = _get_wallet(conn, family_id, int(wallet_id))
        if wallet['currency'] != currency:
            raise ValueError(f'Валюта кошелька должна совпадать с валютой долга: {currency}')
        if _d(wallet['balance']) < amount:
            raise ValueError('Недостаточно средств в кошельке для погашения долга')
        cat_id = _ensure_expense_category(conn, family_id, 'Долги')
        amount_base = _amount_base(family_id, amount, currency)
        tx_id = conn.execute(transactions.insert().values(
            family_id=family_id, user_id=user['id'], type='expense', amount=amount, currency=currency,
            amount_base=amount_base, wallet_id=wallet_id, category_id=cat_id,
            transfer_id=None, comment=f'Погашение долга: {d["name"]}', created_at=_now()
        )).inserted_primary_key[0]
        conn.execute(update(wallets).where(wallets.c.id == wallet_id).values(balance=_d(wallet['balance']) - amount))
        conn.execute(update(debts).where(debts.c.id == debt_id).values(
            paid_amount=(_d(d['paid_amount']) + amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            paid_base=(_d(d['paid_base']) + amount_base).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        ))
        payment_id = conn.execute(debt_payments.insert().values(
            family_id=family_id, user_id=user['id'], debt_id=debt_id, wallet_id=wallet_id,
            transaction_id=tx_id, amount=amount, currency=currency, amount_base=amount_base, created_at=_now()
        )).inserted_primary_key[0]
        _log(conn, user, 'pay', 'debt', int(debt_id), f'payment={payment_id}; tx={tx_id}; amount={amount} {currency}')
        return int(payment_id)


def add_goal_money(user: dict, goal_id: int, amount: float, wallet_id: int | None = None):
    """Пополнение цели обязательно через кошелек. Операция и вклад откатываются вместе."""
    require_permission(user, 'manage_goals')
    family_id = int(user['family_id'])
    amount = validate_amount(amount)
    if not wallet_id:
        raise ValueError('Для пополнения цели нужно выбрать кошелек')
    with engine.begin() as conn:
        g = conn.execute(select(goals).where(and_(goals.c.id == goal_id, goals.c.family_id == family_id))).first()
        if not g:
            raise ValueError('Цель не найдена')
        goal = g._mapping
        currency = validate_currency(goal['currency'])
        wallet = _get_wallet(conn, family_id, int(wallet_id))
        if wallet['currency'] != currency:
            raise ValueError(f'Валюта кошелька должна совпадать с валютой цели: {currency}')
        if _d(wallet['balance']) < amount:
            raise ValueError('Недостаточно средств в кошельке для пополнения цели')
        left = _d(goal['target_amount']) - _d(goal['current_amount'])
        if left <= 0:
            raise ValueError('Цель уже достигнута')
        if amount > left:
            amount = left.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        cat_id = _ensure_expense_category(conn, family_id, 'Накопления')
        amount_base = _amount_base(family_id, amount, currency)
        tx_id = conn.execute(transactions.insert().values(
            family_id=family_id, user_id=user['id'], type='expense', amount=amount, currency=currency,
            amount_base=amount_base, wallet_id=int(wallet_id), category_id=cat_id,
            transfer_id=None, comment=f'Пополнение цели: {goal["name"]}', created_at=_now()
        )).inserted_primary_key[0]
        conn.execute(update(wallets).where(wallets.c.id == int(wallet_id)).values(balance=_d(wallet['balance']) - amount))
        contribution_id = conn.execute(goal_contributions.insert().values(
            family_id=family_id, user_id=user['id'], goal_id=goal_id, wallet_id=int(wallet_id),
            transaction_id=int(tx_id), amount=amount, currency=currency, created_at=_now()
        )).inserted_primary_key[0]
        conn.execute(update(goals).where(goals.c.id == goal_id).values(current_amount=_d(goal['current_amount']) + amount))
        _log(conn, user, 'add_money', 'goal', int(goal_id), f'contribution={contribution_id}; tx={tx_id}; {amount} {currency}; wallet={wallet_id}')
        return int(contribution_id)


_prev_safe_migrations_l40 = _prev_safe_migrations_l35

def admin_log(action: str, *, admin_label: str = 'admin', ip_address: str = '', entity_type: str = 'system', entity_id: int | None = None, details: str = ''):
    with engine.begin() as conn:
        conn.execute(admin_audit_logs.insert().values(
            admin_label=_clean_text(admin_label, 120),
            ip_address=_clean_text(ip_address, 80),
            action=_clean_text(action, 80),
            entity_type=_clean_text(entity_type, 80),
            entity_id=entity_id,
            details=_clean_text(details, 2000),
            created_at=_now(),
        ))

def get_admin_audit_logs(limit: int = 200):
    limit = max(1, min(int(limit or 200), 1000))
    with engine.begin() as conn:
        rows = conn.execute(select(admin_audit_logs).order_by(admin_audit_logs.c.id.desc()).limit(limit)).all()
    return _rows(rows)

def get_audit_logs_filtered(family_id: int, *, action: str = '', user_id=None, entity_type: str = '', entity_id=None, date_from=None, date_to=None, limit: int = 200):
    limit = max(1, min(int(limit or 200), 1000))
    cond = [audit_logs.c.family_id == int(family_id)]
    if action:
        cond.append(audit_logs.c.action == _clean_text(action, 64))
    if entity_type:
        cond.append(audit_logs.c.entity_type == _clean_text(entity_type, 64))
    if entity_id:
        cond.append(audit_logs.c.entity_id == int(entity_id))
    if user_id:
        cond.append(audit_logs.c.user_id == int(user_id))
    if date_from:
        cond.append(audit_logs.c.created_at >= validate_date(date_from, 'Дата с'))
    if date_to:
        cond.append(audit_logs.c.created_at < validate_date(date_to, 'Дата по') + timedelta(days=1))
    with engine.begin() as conn:
        rows = conn.execute(select(
            audit_logs.c.id, audit_logs.c.action, audit_logs.c.entity_type, audit_logs.c.entity_id,
            audit_logs.c.details, audit_logs.c.created_at, users.c.full_name.label('user_name')
        ).select_from(audit_logs.outerjoin(users, users.c.id == audit_logs.c.user_id))
         .where(and_(*cond)).order_by(audit_logs.c.id.desc()).limit(limit)).all()
    return _rows(rows)

def get_operation_history(user: dict, transaction_id: int):
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        tx = conn.execute(select(transactions.c.id).where(and_(transactions.c.id == int(transaction_id), transactions.c.family_id == family_id))).first()
        # Даже если операция удалена, история по id может быть полезной, поэтому не падаем.
        rows = conn.execute(select(
            audit_logs.c.id, audit_logs.c.action, audit_logs.c.entity_type, audit_logs.c.entity_id,
            audit_logs.c.details, audit_logs.c.created_at, users.c.full_name.label('user_name')
        ).select_from(audit_logs.outerjoin(users, users.c.id == audit_logs.c.user_id))
         .where(and_(audit_logs.c.family_id == family_id, audit_logs.c.entity_type == 'transaction', audit_logs.c.entity_id == int(transaction_id)))
         .order_by(audit_logs.c.id.desc())).all()
    return _rows(rows)

def _extract_detail_int(details: str, key: str):
    m = _re_l40.search(rf'{_re_l40.escape(key)}=(\d+)', str(details or ''))
    return int(m.group(1)) if m else None


# --- Level 4.1: product admin dashboard, user blocking, audit export and compensating undo ---

def _ensure_l41_columns():
    """Small compatibility migration for Level 4.1. Alembic migration is also included."""
    with engine.begin() as conn:
        if inspect(engine).has_table('users') and not _has_column('users', 'is_blocked'):
            conn.execute(text('ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0 NOT NULL'))
        if inspect(engine).has_table('notification_settings') and not _has_column('notification_settings', 'scheduled_payment_enabled'):
            conn.execute(text('ALTER TABLE notification_settings ADD COLUMN scheduled_payment_enabled INTEGER DEFAULT 1 NOT NULL'))
        if inspect(engine).has_table('transactions') and not _has_column('transactions', 'undo_of_audit_id'):
            conn.execute(text('ALTER TABLE transactions ADD COLUMN undo_of_audit_id INTEGER'))
        if inspect(engine).has_table('transfers') and not _has_column('transfers', 'undo_of_audit_id'):
            conn.execute(text('ALTER TABLE transfers ADD COLUMN undo_of_audit_id INTEGER'))
        if inspect(engine).has_table('transactions') and not _has_column('transactions', 'scheduled_payment_id'):
            conn.execute(text('ALTER TABLE transactions ADD COLUMN scheduled_payment_id INTEGER'))
        if inspect(engine).has_table('wallets') and not _has_column('wallets', 'include_in_free_money'):
            conn.execute(text('ALTER TABLE wallets ADD COLUMN include_in_free_money INTEGER DEFAULT 1 NOT NULL'))
        if inspect(engine).has_table('audit_logs') and not _has_column('audit_logs', 'resolved_at'):
            conn.execute(text('ALTER TABLE audit_logs ADD COLUMN resolved_at DATETIME'))

_prev_safe_migrations_l41 = _prev_safe_migrations_l35

try:
    _ensure_l41_columns()
except Exception:
    pass


def _user_blocked_value(user_id: int) -> int:
    if not _has_column('users', 'is_blocked'):
        return 0
    with engine.begin() as conn:
        row = conn.execute(select(users.c.id, text('is_blocked')).where(users.c.id == int(user_id))).first()
        return int(row._mapping.get('is_blocked') or 0) if row else 0


def is_user_blocked(user: dict | int) -> bool:
    uid = int(user.get('id') if isinstance(user, dict) else user)
    return _user_blocked_value(uid) == 1


def admin_set_user_blocked(user_id: int, blocked: bool):
    if not _has_column('users', 'is_blocked'):
        _ensure_l41_columns()
    with engine.begin() as conn:
        row = conn.execute(select(users.c.id).where(users.c.id == int(user_id))).first()
        if not row:
            raise ValueError('Пользователь не найден')
        conn.execute(text('UPDATE users SET is_blocked = :blocked WHERE id = :id'), {'blocked': 1 if blocked else 0, 'id': int(user_id)})
    return True


def get_admin_users(limit: int = 200):
    limit = max(1, min(int(limit or 200), 500))
    with engine.begin() as conn:
        if _has_column('users', 'is_blocked'):
            rows = conn.execute(text('SELECT id, telegram_id, full_name, role, family_id, created_at, is_blocked FROM users ORDER BY id DESC LIMIT :limit'), {'limit': limit}).fetchall()
            return [{k: _jsonable(v) for k, v in dict(r._mapping).items()} for r in rows]
        rows = conn.execute(select(users.c.id, users.c.telegram_id, users.c.full_name, users.c.role, users.c.family_id, users.c.created_at).order_by(users.c.id.desc()).limit(limit)).fetchall()
        result = _rows(rows)
        for r in result:
            r['is_blocked'] = 0
        return result


def get_admin_chart_data(days: int = 30):
    days = max(7, min(int(days or 30), 90))
    start = datetime.now() - timedelta(days=days-1)
    start = datetime(start.year, start.month, start.day)
    labels = []
    series = {}
    cur = start
    for _ in range(days):
        key = cur.strftime('%Y-%m-%d')
        labels.append(key[5:])
        series[key] = {'income': 0.0, 'expense': 0.0, 'transactions': 0}
        cur += timedelta(days=1)
    with engine.begin() as conn:
        rows = conn.execute(select(transactions.c.type, transactions.c.amount_base, transactions.c.created_at).where(transactions.c.created_at >= start)).all()
        fam_rows = conn.execute(select(families.c.created_at).where(families.c.created_at >= start)).all()
        user_rows = conn.execute(select(users.c.created_at).where(users.c.created_at >= start)).all()
    new_families = {k: 0 for k in series}
    new_users = {k: 0 for k in series}
    for r in rows:
        m = r._mapping
        key = m['created_at'].strftime('%Y-%m-%d')
        if key in series:
            if m['type'] in ('income', 'expense'):
                series[key][m['type']] += float(m['amount_base'] or 0)
            series[key]['transactions'] += 1
    for r in fam_rows:
        key = r._mapping['created_at'].strftime('%Y-%m-%d')
        if key in new_families: new_families[key] += 1
    for r in user_rows:
        key = r._mapping['created_at'].strftime('%Y-%m-%d')
        if key in new_users: new_users[key] += 1
    return {
        'labels': labels,
        'income': [round(series[k]['income'], 2) for k in series],
        'expense': [round(series[k]['expense'], 2) for k in series],
        'transactions': [series[k]['transactions'] for k in series],
        'new_families': [new_families[k] for k in series],
        'new_users': [new_users[k] for k in series],
    }


def get_admin_stats():
    with engine.begin() as conn:
        family_count = conn.execute(select(func.count()).select_from(families)).scalar() or 0
        user_count = conn.execute(select(func.count()).select_from(users)).scalar() or 0
        blocked_count = 0
        if _has_column('users', 'is_blocked'):
            blocked_count = conn.execute(text('SELECT COUNT(*) FROM users WHERE is_blocked = 1')).scalar() or 0
        wallet_count = conn.execute(select(func.count()).select_from(wallets)).scalar() or 0
        tx_count = conn.execute(select(func.count()).select_from(transactions)).scalar() or 0
        debt_count = conn.execute(select(func.count()).select_from(debts)).scalar() or 0
        goal_count = conn.execute(select(func.count()).select_from(goals)).scalar() or 0
        income = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(transactions.c.type == 'income')).scalar() or 0
        expense = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(transactions.c.type == 'expense')).scalar() or 0
    return {
        'families': int(family_count), 'users': int(user_count), 'blocked_users': int(blocked_count),
        'wallets': int(wallet_count), 'transactions': int(tx_count), 'debts': int(debt_count), 'goals': int(goal_count),
        'income_base': round(float(income), 2), 'expense_base': round(float(expense), 2),
        'balance_base': round(float(income) - float(expense), 2), 'database': engine.url.get_backend_name(),
    }


def get_admin_family_operations(family_id: int, *, q: str = '', tx_type: str = '', user_id=None, date_from=None, date_to=None, limit=200):
    return get_transactions_filtered(int(family_id), q=q, tx_type=tx_type, user_id=user_id, date_from=date_from, date_to=date_to, limit=limit)


def get_admin_family_detail(family_id: int):
    family_id = int(family_id)
    return {
        'family': get_family(family_id),
        'members': get_members(family_id),
        'wallets': get_wallet_report(family_id),
        'rates': get_rates(family_id),
        'summary': get_summary(family_id),
        'month_summary': get_month_summary(family_id),
        'category_report': get_expense_by_categories(family_id),
        'daily_chart': get_daily_chart(family_id),
        'recent': get_recent_transactions(family_id, 100),
        'debts': get_debts(family_id),
        'goals': get_goals(family_id),
        'budgets': get_budgets(family_id),
        'audit_logs': get_audit_logs_filtered(family_id, limit=100),
    }


def get_admin_audit_logs_filtered(*, action: str = '', admin_label: str = '', entity_type: str = '', date_from=None, date_to=None, limit: int = 500):
    limit = max(1, min(int(limit or 500), 5000))
    cond = []
    if action:
        cond.append(admin_audit_logs.c.action == _clean_text(action, 80))
    if admin_label:
        cond.append(admin_audit_logs.c.admin_label == _clean_text(admin_label, 120))
    if entity_type:
        cond.append(admin_audit_logs.c.entity_type == _clean_text(entity_type, 80))
    if date_from:
        cond.append(admin_audit_logs.c.created_at >= validate_date(date_from, 'Дата с'))
    if date_to:
        cond.append(admin_audit_logs.c.created_at < validate_date(date_to, 'Дата по') + timedelta(days=1))
    with engine.begin() as conn:
        stmt = select(admin_audit_logs).order_by(admin_audit_logs.c.id.desc()).limit(limit)
        if cond:
            stmt = select(admin_audit_logs).where(and_(*cond)).order_by(admin_audit_logs.c.id.desc()).limit(limit)
        rows = conn.execute(stmt).all()
    return _rows(rows)


def _admin_log_rows_for_export(**kwargs):
    return get_admin_audit_logs_filtered(**kwargs)


def _opposite_type(tx_type: str) -> str:
    if tx_type == 'income': return 'expense'
    if tx_type == 'expense': return 'income'
    raise ValueError('Можно компенсировать только income/expense')


def _insert_compensation_tx(conn, user: dict, original, *, audit_id: int, comment_prefix='UNDO') -> int:
    t = original._mapping if hasattr(original, '_mapping') else original
    family_id = int(user['family_id'])
    wallet = _get_wallet(conn, family_id, int(t['wallet_id']))
    amount = _d(t['amount'])
    comp_type = _opposite_type(t['type'])
    if comp_type == 'expense' and _d(wallet['balance']) < amount:
        raise ValueError('Нельзя сделать undo: для компенсационной расходной операции недостаточно средств')
    tx_id = conn.execute(transactions.insert().values(
        family_id=family_id, user_id=user['id'], type=comp_type, amount=amount, currency=t['currency'],
        amount_base=t['amount_base'], wallet_id=t['wallet_id'], category_id=t['category_id'], transfer_id=None,
        comment=f'{comment_prefix} audit#{audit_id}: {t.get("comment") or ""}'[:300], created_at=_now(),
        # undo_of_audit_id is kept in DB for future ORM use; audit log stores the link for MVP.
    )).inserted_primary_key[0]
    delta = amount if comp_type == 'income' else -amount
    conn.execute(update(wallets).where(wallets.c.id == wallet['id']).values(balance=_d(wallet['balance']) + delta))
    _log(conn, user, 'compensate', 'transaction', int(tx_id), f'undo_of_audit={audit_id}; original_tx={t["id"]}; {comp_type} {amount} {t["currency"]}')
    return int(tx_id)


def undo_audit_action(user: dict, audit_id: int):
    """Level 4.1 undo: never deletes original records. Creates compensation operations instead."""
    require_permission(user, 'add_transaction')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        row = conn.execute(select(audit_logs).where(and_(audit_logs.c.id == int(audit_id), audit_logs.c.family_id == family_id))).first()
        if not row:
            raise ValueError('Действие для отмены не найдено')
        a = row._mapping
        action, entity_type, entity_id, details = a['action'], a['entity_type'], a['entity_id'], a['details'] or ''
        already = conn.execute(select(audit_logs.c.id).where(and_(audit_logs.c.family_id == family_id, audit_logs.c.action == 'undo', audit_logs.c.entity_type == 'audit_log', audit_logs.c.entity_id == int(audit_id)))).first()
        if already:
            raise ValueError('Это действие уже было отменено')
        if action == 'create' and entity_type == 'transaction' and entity_id:
            tx = conn.execute(select(transactions).where(and_(transactions.c.id == int(entity_id), transactions.c.family_id == family_id))).first()
            if not tx:
                raise ValueError('Исходная операция уже не найдена')
            if tx._mapping.get('transfer_id'):
                raise ValueError('Для перевода используйте undo действия transfer')
            comp_id = _insert_compensation_tx(conn, user, tx, audit_id=int(audit_id))
            _log(conn, user, 'undo', 'audit_log', int(audit_id), f'compensation_tx={comp_id}; original_action={action}:{entity_type}:{entity_id}')
            return True
        if action == 'create' and entity_type == 'transfer' and entity_id:
            tr = conn.execute(select(transfers).where(and_(transfers.c.id == int(entity_id), transfers.c.family_id == family_id))).first()
            if not tr:
                raise ValueError('Исходный перевод не найден')
            t = tr._mapping
            # Reverse transfer, no deletion.
            src = _get_wallet(conn, family_id, int(t['to_wallet_id']))
            dst = _get_wallet(conn, family_id, int(t['from_wallet_id']))
            amount_from = _d(t['amount_to'])
            amount_to = _d(t['amount_from'])
            if _d(src['balance']) < amount_from:
                raise ValueError('Нельзя сделать undo перевода: в кошельке-получателе недостаточно средств')
            rev_id = conn.execute(transfers.insert().values(
                family_id=family_id, user_id=user['id'], from_wallet_id=src['id'], to_wallet_id=dst['id'],
                amount_from=amount_from, currency_from=src['currency'], amount_to=amount_to, currency_to=dst['currency'],
                amount_base=t['amount_base'], comment=f'UNDO audit#{audit_id}: {t.get("comment") or ""}'[:300], created_at=_now(),
                # undo_of_audit_id is kept in DB for future ORM use; audit log stores the link for MVP.
            )).inserted_primary_key[0]
            conn.execute(update(wallets).where(wallets.c.id == src['id']).values(balance=_d(src['balance']) - amount_from))
            conn.execute(update(wallets).where(wallets.c.id == dst['id']).values(balance=_d(dst['balance']) + amount_to))
            out_id = conn.execute(transactions.insert().values(family_id=family_id, user_id=user['id'], type='transfer_out', amount=amount_from, currency=src['currency'], amount_base=t['amount_base'], wallet_id=src['id'], category_id=None, transfer_id=rev_id, comment=f'UNDO transfer #{entity_id}', created_at=_now())).inserted_primary_key[0]
            in_id = conn.execute(transactions.insert().values(family_id=family_id, user_id=user['id'], type='transfer_in', amount=amount_to, currency=dst['currency'], amount_base=t['amount_base'], wallet_id=dst['id'], category_id=None, transfer_id=rev_id, comment=f'UNDO transfer #{entity_id}', created_at=_now())).inserted_primary_key[0]
            _log(conn, user, 'create', 'transfer', int(rev_id), f'undo_of_audit={audit_id}; reverse_of={entity_id}; out_tx={out_id}; in_tx={in_id}')
            _log(conn, user, 'undo', 'audit_log', int(audit_id), f'compensation_transfer={rev_id}; original_transfer={entity_id}')
            return True
        if action == 'pay' and entity_type == 'debt':
            tx_id = _extract_detail_int(details, 'tx')
            if not tx_id:
                raise ValueError('Не найден связанный платеж для отмены')
            tx = conn.execute(select(transactions).where(and_(transactions.c.id == tx_id, transactions.c.family_id == family_id))).first()
            payment = conn.execute(select(debt_payments).where(and_(debt_payments.c.family_id == family_id, debt_payments.c.transaction_id == tx_id))).first()
            if not tx or not payment:
                raise ValueError('Связанный платеж не найден')
            p = payment._mapping
            comp_id = _insert_compensation_tx(conn, user, tx, audit_id=int(audit_id), comment_prefix='UNDO debt payment')
            debt = conn.execute(select(debts).where(and_(debts.c.id == p['debt_id'], debts.c.family_id == family_id))).first()
            if debt:
                d = debt._mapping
                conn.execute(update(debts).where(debts.c.id == p['debt_id']).values(
                    paid_amount=max(Decimal('0'), _d(d['paid_amount']) - _d(p['amount'])),
                    paid_base=max(Decimal('0'), _d(d['paid_base']) - _d(p['amount_base'])),
                ))
            _log(conn, user, 'undo', 'audit_log', int(audit_id), f'compensation_tx={comp_id}; debt_payment={p["id"]}')
            return True
        if action == 'add_money' and entity_type == 'goal':
            tx_id = _extract_detail_int(details, 'tx')
            if not tx_id:
                raise ValueError('Не найдено связанное пополнение цели для отмены')
            tx = conn.execute(select(transactions).where(and_(transactions.c.id == tx_id, transactions.c.family_id == family_id))).first()
            contribution = conn.execute(select(goal_contributions).where(and_(goal_contributions.c.family_id == family_id, goal_contributions.c.transaction_id == tx_id))).first()
            if not tx or not contribution:
                raise ValueError('Связанное пополнение цели не найдено')
            c = contribution._mapping
            comp_id = _insert_compensation_tx(conn, user, tx, audit_id=int(audit_id), comment_prefix='UNDO goal contribution')
            goal = conn.execute(select(goals).where(and_(goals.c.id == c['goal_id'], goals.c.family_id == family_id))).first()
            if goal:
                g = goal._mapping
                conn.execute(update(goals).where(goals.c.id == c['goal_id']).values(current_amount=max(Decimal('0'), _d(g['current_amount']) - _d(c['amount']))))
            _log(conn, user, 'undo', 'audit_log', int(audit_id), f'compensation_tx={comp_id}; goal_contribution={c["id"]}')
            return True
        raise ValueError('Это действие нельзя отменить автоматически')

# --- Level 4.2: production schema mode, unified blocking, DB admin sessions ---
try:
    from config import DB_AUTO_CREATE
except Exception:
    DB_AUTO_CREATE = True

_prev_safe_migrations_l42 = _prev_safe_migrations_l35
def _safe_migrations():
    _prev_safe_migrations_l42()
    # Development/local convenience only. In production, init_db skips this; Alembic owns schema.
    metadata.create_all(engine, tables=[admin_sessions])
    with engine.begin() as conn:
        if inspect(engine).has_table('users') and not _has_column('users', 'is_blocked'):
            conn.execute(text('ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0 NOT NULL'))
        if inspect(engine).has_table('notification_settings') and not _has_column('notification_settings', 'scheduled_payment_enabled'):
            conn.execute(text('ALTER TABLE notification_settings ADD COLUMN scheduled_payment_enabled INTEGER DEFAULT 1 NOT NULL'))
    metadata.create_all(engine, tables=[scheduled_payment_delivery_log, family_member_permission_overrides, ai_personal_rules, budget_wizard_profiles])
    with engine.begin() as conn:
        if inspect(engine).has_table('categories') and not _has_column('categories', 'parent_id'):
            conn.execute(text('ALTER TABLE categories ADD COLUMN parent_id INTEGER'))
        if inspect(engine).has_table('scheduled_payments'):
            for col, ddl in [
                ('wallet_id', 'ALTER TABLE scheduled_payments ADD COLUMN wallet_id INTEGER'),
                ('category_id', 'ALTER TABLE scheduled_payments ADD COLUMN category_id INTEGER'),
                ('auto_create_expense', 'ALTER TABLE scheduled_payments ADD COLUMN auto_create_expense INTEGER DEFAULT 0 NOT NULL'),
                ('last_auto_created_month', 'ALTER TABLE scheduled_payments ADD COLUMN last_auto_created_month VARCHAR(7)'),
            ]:
                if not _has_column('scheduled_payments', col):
                    conn.execute(text(ddl))
        if inspect(engine).has_table('transactions') and not _has_column('transactions', 'scheduled_payment_id'):
            conn.execute(text('ALTER TABLE transactions ADD COLUMN scheduled_payment_id INTEGER'))
        if inspect(engine).has_table('wallets') and not _has_column('wallets', 'include_in_free_money'):
            conn.execute(text('ALTER TABLE wallets ADD COLUMN include_in_free_money INTEGER DEFAULT 1 NOT NULL'))
        if inspect(engine).has_table('audit_logs') and not _has_column('audit_logs', 'resolved_at'):
            conn.execute(text('ALTER TABLE audit_logs ADD COLUMN resolved_at DATETIME'))


def init_db():
    """Initialize DB for local development.

    Level 4.2: In production/Railway set APP_ENV=production or DB_AUTO_CREATE=false.
    Then this function verifies that Alembic already created the schema and does not call create_all().
    """
    if DB_AUTO_CREATE:
        metadata.create_all(engine)
        _safe_migrations()
        return
    # Production safety: never create/alter schema automatically.
    required = ['families', 'users', 'wallets', 'categories', 'transactions', 'audit_logs', 'admin_sessions']
    missing = [t for t in required if not inspect(engine).has_table(t)]
    if missing:
        raise RuntimeError('Database schema is missing tables: ' + ', '.join(missing) + '. Run: alembic upgrade head')


def admin_session_create(session_id: str, csrf: str, is_superadmin: bool, ip_address: str | None, ttl_seconds: int):
    now = _now()
    expires = now + timedelta(seconds=int(ttl_seconds))
    with engine.begin() as conn:
        conn.execute(admin_sessions.insert().values(
            id=session_id, csrf=csrf, is_superadmin=1 if is_superadmin else 0,
            ip_address=_clean_text(ip_address, 64), expires_at=expires, created_at=now,
        ))
    return {'id': session_id, 'csrf': csrf, 'is_superadmin': bool(is_superadmin), 'ip': ip_address, 'expires_at': expires}


def admin_session_get(session_id: str):
    sid = str(session_id or '')
    if not sid:
        return None
    with engine.begin() as conn:
        row = conn.execute(select(admin_sessions).where(admin_sessions.c.id == sid)).first()
        if not row:
            return None
        data = _row(row)
        expires = row._mapping['expires_at']
        if expires < _now():
            conn.execute(delete(admin_sessions).where(admin_sessions.c.id == sid))
            return None
        return {
            'id': sid,
            'csrf': data.get('csrf'),
            'is_superadmin': bool(data.get('is_superadmin')),
            'ip': data.get('ip_address'),
            'expires_at': data.get('expires_at'),
        }


def admin_session_delete(session_id: str):
    sid = str(session_id or '')
    if not sid:
        return
    with engine.begin() as conn:
        conn.execute(delete(admin_sessions).where(admin_sessions.c.id == sid))


def admin_session_purge_expired():
    with engine.begin() as conn:
        conn.execute(delete(admin_sessions).where(admin_sessions.c.expires_at < _now()))

# --- Level 4.3: WebApp analytics, budget notification cooldown, forecasts ---
def ensure_level4_3_tables():
    metadata.create_all(engine, tables=[budget_notification_events])

def get_monthly_trend(family_id: int, months_count: int = 6):
    today = date.today().replace(day=1)
    labels = []
    results = []
    for i in range(months_count - 1, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        ym = f'{y:04d}-{m:02d}'
        labels.append(ym)
        results.append(get_month_summary(family_id, ym))
    return {
        'labels': labels,
        'income': [round(float(x.get('income') or 0), 2) for x in results],
        'expense': [round(float(x.get('expense') or 0), 2) for x in results],
        'balance': [round(float(x.get('balance') or 0), 2) for x in results],
    }

def get_budget_usage_chart(family_id: int, ym=None):
    rows = get_budgets(family_id, ym)
    return {
        'labels': [str(x.get('category_name') or '') for x in rows],
        'limit': [round(float(x.get('limit_base') or 0), 2) for x in rows],
        'spent': [round(float(x.get('spent_base') or 0), 2) for x in rows],
        'percent': [round(float(x.get('percent') or 0), 2) for x in rows],
    }

def get_webapp_chart_pack(family_id: int, ym=None, date_from=None, date_to=None):
    return {
        'daily': get_daily_chart(family_id, ym, date_from, date_to),
        'categories': get_expense_by_categories(family_id, ym, date_from, date_to),
        'monthly_trend': get_monthly_trend(family_id, 6),
        'budget_usage': get_budget_usage_chart(family_id, ym),
        'wallets': get_wallet_report(family_id),
        'currencies': get_currency_report(family_id, ym, date_from, date_to),
    }

def get_expense_forecast(family_id: int, ym=None):
    ym = validate_month(ym)
    y, m = [int(x) for x in ym.split('-')]
    start = datetime(y, m, 1)
    if m == 12:
        end = datetime(y + 1, 1, 1)
    else:
        end = datetime(y, m + 1, 1)
    today = date.today()
    days_in_month = (end.date() - start.date()).days
    if today.year == y and today.month == m:
        elapsed = max(1, min(today.day, days_in_month))
    elif today < start.date():
        elapsed = 0
    else:
        elapsed = days_in_month
    with engine.begin() as conn:
        spent = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(and_(transactions.c.family_id == family_id, transactions.c.type == 'expense', transactions.c.created_at >= start, transactions.c.created_at < min(end, datetime.combine(today + timedelta(days=1), datetime.min.time()))))).scalar() or 0
        rows = conn.execute(select(categories.c.name.label('category_name'), func.coalesce(func.sum(transactions.c.amount_base), 0).label('amount')).select_from(transactions.join(categories, categories.c.id == transactions.c.category_id)).where(and_(transactions.c.family_id == family_id, transactions.c.type == 'expense', transactions.c.created_at >= start, transactions.c.created_at < min(end, datetime.combine(today + timedelta(days=1), datetime.min.time())))).group_by(categories.c.name).order_by(text('amount DESC'))).all()
    spent = float(spent or 0)
    daily_avg = spent / elapsed if elapsed else 0
    projected = daily_avg * days_in_month if elapsed else 0
    categories_forecast = []
    for r in rows:
        amount = float(r._mapping['amount'] or 0)
        cat_daily = amount / elapsed if elapsed else 0
        categories_forecast.append({
            'category_name': r._mapping['category_name'],
            'spent': round(amount, 2),
            'projected': round(cat_daily * days_in_month, 2),
        })
    return {
        'month': ym,
        'spent_so_far': round(spent, 2),
        'elapsed_days': elapsed,
        'days_in_month': days_in_month,
        'daily_avg': round(daily_avg, 2),
        'projected_expense': round(projected, 2),
        'remaining_days': max(0, days_in_month - elapsed),
        'categories': categories_forecast[:10],
    }

def get_budget_alerts_detailed(family_id: int, ym=None, threshold: float = 100):
    alerts = []
    for b in get_budgets(family_id, ym):
        try:
            pct = float(b.get('percent') or 0)
            if pct >= threshold:
                alerts.append({
                    'budget_id': int(b.get('id')),
                    'family_id': int(family_id),
                    'category_name': b.get('category_name'),
                    'percent': round(pct, 2),
                    'spent_base': round(float(b.get('spent_base') or 0), 2),
                    'limit_base': round(float(b.get('limit_base') or 0), 2),
                    'month': b.get('month'),
                })
        except Exception:
            continue
    return alerts

def should_send_budget_alert(family_id: int, budget_id: int, percent: float, cooldown_hours: int = 12) -> bool:
    ensure_level4_3_tables()
    since = _now() - timedelta(hours=int(cooldown_hours or 12))
    with engine.begin() as conn:
        last = conn.execute(select(budget_notification_events.c.id).where(and_(budget_notification_events.c.family_id == int(family_id), budget_notification_events.c.budget_id == int(budget_id), budget_notification_events.c.created_at >= since)).order_by(budget_notification_events.c.id.desc())).first()
        if last:
            return False
        conn.execute(budget_notification_events.insert().values(family_id=int(family_id), budget_id=int(budget_id), percent=Decimal(str(percent)).quantize(Decimal('0.01')), created_at=_now()))
        return True


# --- Level 4.3.1: notification settings helpers ---
def get_notification_settings(user: dict):
    with engine.begin() as conn:
        row = conn.execute(select(notification_settings).where(notification_settings.c.user_id == int(user['id']))).first()
        if not row:
            conn.execute(notification_settings.insert().values(
                family_id=int(user['family_id']), user_id=int(user['id']), daily_enabled=1, budget_alert_enabled=1, scheduled_payment_enabled=1, created_at=_now()
            ))
            row = conn.execute(select(notification_settings).where(notification_settings.c.user_id == int(user['id']))).first()
        return _row(row)

def update_notification_settings(user: dict, daily_enabled=None, budget_alert_enabled=None, scheduled_payment_enabled=None):
    vals = {}
    if daily_enabled is not None:
        vals['daily_enabled'] = 1 if str(daily_enabled).lower() in {'1','true','yes','on'} else 0
    if budget_alert_enabled is not None:
        vals['budget_alert_enabled'] = 1 if str(budget_alert_enabled).lower() in {'1','true','yes','on'} else 0
    if scheduled_payment_enabled is not None:
        vals['scheduled_payment_enabled'] = 1 if str(scheduled_payment_enabled).lower() in {'1','true','yes','on'} else 0
    if not vals:
        return get_notification_settings(user)
    with engine.begin() as conn:
        row = conn.execute(select(notification_settings).where(notification_settings.c.user_id == int(user['id']))).first()
        if not row:
            conn.execute(notification_settings.insert().values(
                family_id=int(user['family_id']), user_id=int(user['id']), daily_enabled=1, budget_alert_enabled=1, scheduled_payment_enabled=1, created_at=_now()
            ))
        conn.execute(update(notification_settings).where(notification_settings.c.user_id == int(user['id'])).values(**vals))
        _log(conn, user, 'update', 'notification_settings', int(user['id']), str(vals))
        return _row(conn.execute(select(notification_settings).where(notification_settings.c.user_id == int(user['id']))).first())

def get_budget_notification_recipients(family_id: int):
    with engine.begin() as conn:
        q = (select(users.c.telegram_id, users.c.full_name)
             .select_from(users.join(notification_settings, notification_settings.c.user_id == users.c.id))
             .where(and_(users.c.family_id == int(family_id), notification_settings.c.budget_alert_enabled == 1)))
        return _rows(conn.execute(q))


# --- Level 5.2: family member management for the WebApp ---
def update_family_member_role(user: dict, member_id: int, role: str):
    """Change a family member role from the user WebApp. Admin only."""
    require_permission(user, 'manage_family')
    role = _clean_text(role, 24)
    if role not in ALLOWED_ROLES:
        raise ValueError('Неверная роль')
    family_id = int(user['family_id'])
    member_id = int(member_id)
    with engine.begin() as conn:
        member = conn.execute(select(users).where(and_(users.c.id == member_id, users.c.family_id == family_id))).first()
        if not member:
            raise ValueError('Участник не найден')
        current_role = member._mapping['role']
        if member_id == int(user['id']) and current_role == 'admin' and role != 'admin':
            admins = conn.execute(select(func.count()).select_from(users).where(and_(users.c.family_id == family_id, users.c.role == 'admin'))).scalar() or 0
            if admins <= 1:
                raise ValueError('Нельзя снять роль admin с единственного администратора семьи')
        conn.execute(update(users).where(users.c.id == member_id).values(role=role))
        _log(conn, user, 'update_member_role', 'user', member_id, f'{current_role} -> {role}')
    return get_members(family_id)


def remove_family_member(user: dict, member_id: int):
    """Remove a member from current family if it does not break accounting history."""
    require_permission(user, 'manage_family')
    family_id = int(user['family_id'])
    member_id = int(member_id)
    if member_id == int(user['id']):
        raise ValueError('Себя удаляйте через "Удалить мой аккаунт"')
    with engine.begin() as conn:
        member = conn.execute(select(users).where(and_(users.c.id == member_id, users.c.family_id == family_id))).first()
        if not member:
            raise ValueError('Участник не найден')
        if member._mapping['role'] == 'admin':
            admins = conn.execute(select(func.count()).select_from(users).where(and_(users.c.family_id == family_id, users.c.role == 'admin'))).scalar() or 0
            if admins <= 1:
                raise ValueError('Нельзя удалить единственного администратора семьи')
        tx_count = conn.execute(select(func.count()).select_from(transactions).where(transactions.c.user_id == member_id)).scalar() or 0
        transfer_count = conn.execute(select(func.count()).select_from(transfers).where(transfers.c.user_id == member_id)).scalar() or 0
        debt_count = conn.execute(select(func.count()).select_from(debts).where(debts.c.user_id == member_id)).scalar() or 0
        if tx_count or transfer_count or debt_count:
            raise ValueError('У участника есть финансовые записи. Для сохранения истории его нельзя удалить; можно сменить роль на member.')
        conn.execute(delete(notification_settings).where(notification_settings.c.user_id == member_id))
        conn.execute(delete(audit_logs).where(audit_logs.c.user_id == member_id))
        conn.execute(delete(users).where(users.c.id == member_id))
        _log(conn, user, 'remove_member', 'user', member_id, member._mapping['full_name'])
    return get_members(family_id)

# --- Level 5.1: account and family deletion for real-world privacy requirements ---
def delete_my_account(user: dict, confirm: str = ''):
    """Delete current user account.

    If the user is the last family member, deletes the whole family data too.
    Otherwise deletes only user profile and notification settings. Financial
    transactions created by this user are retained for family accounting history
    and their user_id is set to NULL where the schema allows it through audit only;
    transaction rows keep user_id for integrity in older schema, so deletion is
    blocked when user has financial rows unless the whole family is deleted.
    """
    if str(confirm or '').strip().upper() != 'DELETE':
        raise ValueError('Для удаления аккаунта отправьте confirm=DELETE')
    family_id = int(user['family_id'])
    user_id = int(user['id'])
    with engine.begin() as conn:
        member_count = conn.execute(select(func.count()).select_from(users).where(users.c.family_id == family_id)).scalar() or 0
        tx_count = conn.execute(select(func.count()).select_from(transactions).where(transactions.c.user_id == user_id)).scalar() or 0
        transfer_count = conn.execute(select(func.count()).select_from(transfers).where(transfers.c.user_id == user_id)).scalar() or 0
        debt_count = conn.execute(select(func.count()).select_from(debts).where(debts.c.user_id == user_id)).scalar() or 0
        if tx_count or transfer_count or debt_count:
            anon_name = f'Удаленный пользователь #{user_id}'
            conn.execute(update(users).where(users.c.id == user_id).values(telegram_id=-(10_000_000 + user_id), full_name=anon_name, role='member', is_blocked=1))
            conn.execute(delete(notification_settings).where(notification_settings.c.user_id == user_id))
            _log(conn, user, 'anonymize', 'user', user_id, 'account anonymized because financial history exists')
            return {'deleted': 'anonymized', 'user_id': user_id}
        if member_count <= 1:
            _delete_family_cascade(conn, family_id)
            return {'deleted': 'family', 'family_id': family_id}
        conn.execute(delete(notification_settings).where(notification_settings.c.user_id == user_id))
        conn.execute(delete(audit_logs).where(audit_logs.c.user_id == user_id))
        conn.execute(delete(users).where(users.c.id == user_id))
        return {'deleted': 'account', 'user_id': user_id}


def _delete_family_cascade(conn, family_id: int):
    """Hard-delete a family and all its financial data.

    Intended for explicit GDPR/privacy style deletion. A production admin should
    create a backup before calling this endpoint if business policy requires it.
    """
    for table in [
        budget_notification_events,
        scheduled_payment_delivery_log,
        scheduled_payments,
        financial_plan_items,
        debt_payments,
        goal_contributions,
        audit_logs,
        notification_settings,
        budgets,
        transactions,
        transfers,
        debts,
        goals,
        categories,
        wallets,
        exchange_rates,
        users,
    ]:
        if 'family_id' in table.c:
            conn.execute(delete(table).where(table.c.family_id == family_id))
    conn.execute(delete(families).where(families.c.id == family_id))


def delete_my_family(user: dict, confirm: str = ''):
    """Delete the whole current family with all finance data. Admin only."""
    require_permission(user, 'manage_family')
    if str(confirm or '').strip().upper() != 'DELETE FAMILY':
        raise ValueError('Для удаления семьи отправьте confirm=DELETE FAMILY')
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        _delete_family_cascade(conn, family_id)
    return {'deleted': 'family', 'family_id': family_id}


# --- Level 5.3: scheduled payments and financial plan ---
def add_scheduled_payment(user: dict, title: str, amount: float, currency: str, due_day: int, kind: str = 'expense', wallet_id=None, category_id=None, auto_create_expense=False):
    require_permission(user, 'manage_schedules')
    title = _clean_text(title, 160)
    if not title:
        raise ValueError('Название напоминания обязательно')
    amount = _money(amount)
    currency = validate_currency(currency)
    due_day = int(due_day or 1)
    if due_day < 1 or due_day > 31:
        raise ValueError('День платежа должен быть от 1 до 31')
    kind = str(kind or 'expense').strip()[:32]
    wallet_id = int(wallet_id) if wallet_id else None
    category_id = int(category_id) if category_id else None
    auto_create_expense = 1 if auto_create_expense else 0
    with engine.begin() as conn:
        if auto_create_expense:
            if not wallet_id or not category_id:
                raise ValueError('Для автосоздания расхода нужно выбрать кошелек и категорию')
            wallet = _get_wallet(conn, int(user['family_id']), wallet_id)
            if wallet['currency'] != currency:
                raise ValueError('Валюта кошелька должна совпадать с валютой платежа')
            if not family_owns_category(int(user['family_id']), category_id, 'expense'):
                raise ValueError('Категория расхода не найдена')
        sid = conn.execute(scheduled_payments.insert().values(
            family_id=int(user['family_id']), user_id=int(user['id']), title=title,
            amount=amount, currency=currency, kind=kind, wallet_id=wallet_id, category_id=category_id,
            auto_create_expense=auto_create_expense, last_auto_created_month=None, due_day=due_day, enabled=1,
            last_sent_month=None, created_at=_now()
        )).inserted_primary_key[0]
        _log(conn, user, 'create', 'scheduled_payment', int(sid), f'{title} day={due_day}')
        return int(sid)

def update_scheduled_payment(user: dict, schedule_id: int, title=None, amount=None, currency=None, due_day=None, enabled=None, kind=None, wallet_id=None, category_id=None, auto_create_expense=None):
    require_permission(user, 'manage_schedules')
    vals = {}
    if title is not None:
        title = _clean_text(title, 160)
        if not title: raise ValueError('Название напоминания обязательно')
        vals['title'] = title
    if amount is not None: vals['amount'] = _money(amount)
    if currency is not None: vals['currency'] = validate_currency(currency)
    if due_day is not None:
        day = int(due_day)
        if day < 1 or day > 31: raise ValueError('День платежа должен быть от 1 до 31')
        vals['due_day'] = day
    if enabled is not None: vals['enabled'] = 1 if str(enabled).lower() in {'1','true','yes','on'} else 0
    if kind is not None: vals['kind'] = _clean_text(kind, 32)
    if wallet_id is not None: vals['wallet_id'] = int(wallet_id) if wallet_id else None
    if category_id is not None: vals['category_id'] = int(category_id) if category_id else None
    if auto_create_expense is not None: vals['auto_create_expense'] = 1 if str(auto_create_expense).lower() in {'1','true','yes','on'} else 0
    with engine.begin() as conn:
        row = conn.execute(select(scheduled_payments).where(and_(scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('Напоминание не найдено')
        if vals:
            current = row._mapping
            merged = {k: current.get(k) for k in current.keys()}
            merged.update(vals)
            if int(merged.get('auto_create_expense') or 0) == 1:
                wid = int(merged['wallet_id']) if merged.get('wallet_id') else None
                cid = int(merged['category_id']) if merged.get('category_id') else None
                if not wid or not cid:
                    raise ValueError('Для автосоздания расхода нужно выбрать кошелек и категорию')
                wallet = _get_wallet(conn, int(user['family_id']), wid)
                if wallet['currency'] != merged.get('currency'):
                    raise ValueError('Валюта кошелька должна совпадать с валютой платежа')
                if not family_owns_category(int(user['family_id']), cid, 'expense'):
                    raise ValueError('Категория расхода не найдена')
            conn.execute(update(scheduled_payments).where(scheduled_payments.c.id == int(schedule_id)).values(**vals))
            _log(conn, user, 'edit', 'scheduled_payment', int(schedule_id), str(vals))
        return True

def delete_scheduled_payment(user: dict, schedule_id: int):
    require_permission(user, 'manage_schedules')
    with engine.begin() as conn:
        row = conn.execute(select(scheduled_payments).where(and_(scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('Напоминание не найдено')
        conn.execute(delete(scheduled_payments).where(scheduled_payments.c.id == int(schedule_id)))
        _log(conn, user, 'delete', 'scheduled_payment', int(schedule_id), row._mapping['title'])
        return True

def get_scheduled_payments(family_id: int):
    with engine.begin() as conn:
        return _rows(conn.execute(select(scheduled_payments).where(scheduled_payments.c.family_id == int(family_id)).order_by(scheduled_payments.c.due_day, scheduled_payments.c.id)))

def get_due_scheduled_payments(today=None):
    today = today or date.today()
    ym = today.strftime('%Y-%m')
    day = int(today.day)
    with engine.begin() as conn:
        delivered = select(scheduled_payment_delivery_log.c.id).where(and_(
            scheduled_payment_delivery_log.c.schedule_id == scheduled_payments.c.id,
            scheduled_payment_delivery_log.c.user_id == users.c.id,
            scheduled_payment_delivery_log.c.month == ym,
            scheduled_payment_delivery_log.c.status == 'sent',
        )).exists()
        q = (select(scheduled_payments, users.c.id.label('recipient_user_id'), users.c.telegram_id, users.c.full_name)
             .select_from(scheduled_payments.join(users, users.c.family_id == scheduled_payments.c.family_id))
             .join(notification_settings, notification_settings.c.user_id == users.c.id)
             .where(and_(
                 scheduled_payments.c.enabled == 1,
                 scheduled_payments.c.due_day <= day,
                 notification_settings.c.scheduled_payment_enabled == 1,
                 users.c.is_blocked == 0,
                 ~delivered,
             )))
        return _rows(conn.execute(q))

def log_scheduled_payment_delivery(schedule_id: int, user_id: int, telegram_id: int, family_id: int, month: str | None = None, status: str = 'sent', error: str = ''):
    month = month or date.today().strftime('%Y-%m')
    status = _clean_text(status, 32) or 'sent'
    error = _clean_text(error, 500)
    with engine.begin() as conn:
        exists = conn.execute(select(scheduled_payment_delivery_log.c.id).where(and_(
            scheduled_payment_delivery_log.c.schedule_id == int(schedule_id),
            scheduled_payment_delivery_log.c.user_id == int(user_id),
            scheduled_payment_delivery_log.c.month == month,
            scheduled_payment_delivery_log.c.status == status,
        ))).first()
        if not exists:
            conn.execute(scheduled_payment_delivery_log.insert().values(
                family_id=int(family_id), schedule_id=int(schedule_id), user_id=int(user_id), telegram_id=int(telegram_id),
                month=month, status=status, error=error, sent_at=_now()
            ))
        # Compatibility field for old reports/admin views: mark only when all enabled recipients were delivered.
        total = conn.execute(select(func.count()).select_from(users.join(notification_settings, notification_settings.c.user_id == users.c.id)).where(and_(users.c.family_id == int(family_id), users.c.is_blocked == 0, notification_settings.c.scheduled_payment_enabled == 1))).scalar() or 0
        sent = conn.execute(select(func.count()).select_from(scheduled_payment_delivery_log).where(and_(scheduled_payment_delivery_log.c.schedule_id == int(schedule_id), scheduled_payment_delivery_log.c.month == month, scheduled_payment_delivery_log.c.status == 'sent'))).scalar() or 0
        if total and sent >= total:
            conn.execute(update(scheduled_payments).where(scheduled_payments.c.id == int(schedule_id)).values(last_sent_month=month))
        return True

def mark_scheduled_payment_sent(schedule_id: int, month: str | None = None):
    # Backward-compatible helper: prefer log_scheduled_payment_delivery for per-user delivery tracking.
    month = month or date.today().strftime('%Y-%m')
    with engine.begin() as conn:
        conn.execute(update(scheduled_payments).where(scheduled_payments.c.id == int(schedule_id)).values(last_sent_month=month))
        return True


def _create_scheduled_payment_transaction(conn, user: dict, schedule_row, *, wallet_id=None, category_id=None, comment_prefix='Оплата обязательного платежа'):
    m = schedule_row._mapping if hasattr(schedule_row, '_mapping') else schedule_row
    family_id = int(user['family_id'])
    sid = int(m['id'])
    ym = date.today().strftime('%Y-%m')
    start, end = _month_range(ym)[1:]
    existing = conn.execute(select(transactions.c.id).where(and_(
        transactions.c.family_id == family_id, transactions.c.scheduled_payment_id == sid,
        transactions.c.created_at >= start, transactions.c.created_at < end
    ))).first()
    if existing:
        raise ValueError('Этот обязательный платеж уже отмечен оплаченным в этом месяце')
    wid = int(wallet_id or m.get('wallet_id') or 0)
    cid = int(category_id or m.get('category_id') or 0)
    if not wid or not cid:
        raise ValueError('Для оплаты обязательного платежа выберите кошелек и категорию')
    wallet = _get_wallet(conn, family_id, wid)
    currency = validate_currency(m.get('currency') or wallet['currency'])
    if wallet['currency'] != currency:
        raise ValueError('Валюта кошелька должна совпадать с валютой платежа')
    if not family_owns_category(family_id, cid, 'expense'):
        raise ValueError('Категория расхода не найдена')
    amount = _d(m.get('amount') or 0)
    if _d(wallet['balance']) < amount:
        raise ValueError('Недостаточно средств в кошельке')
    tx_id = conn.execute(transactions.insert().values(
        family_id=family_id, user_id=int(user['id']), type='expense', amount=amount,
        currency=currency, amount_base=_amount_base(family_id, amount, currency),
        wallet_id=wid, category_id=cid, transfer_id=None, scheduled_payment_id=sid,
        comment=f"{comment_prefix}: {m.get('title')} ({ym})", created_at=_now()
    )).inserted_primary_key[0]
    conn.execute(update(wallets).where(wallets.c.id == wid).values(balance=_d(wallet['balance']) - amount))
    _log(conn, user, 'pay', 'scheduled_payment', sid, f'tx={tx_id}; {amount} {currency}')
    return int(tx_id)

def pay_mandatory_payment(user: dict, schedule_id: int, wallet_id=None, category_id=None):
    require_permission(user, 'manage_schedules')
    with engine.begin() as conn:
        row = conn.execute(select(scheduled_payments).where(and_(
            scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id']),
            scheduled_payments.c.enabled == 1
        ))).first()
        if not row: raise ValueError('Обязательный платеж не найден')
        return _create_scheduled_payment_transaction(conn, user, row, wallet_id=wallet_id, category_id=category_id, comment_prefix='Оплата обязательного платежа')

def mark_mandatory_payment_paid(user: dict, schedule_id: int, wallet_id=None, category_id=None):
    require_permission(user, 'manage_schedules')
    with engine.begin() as conn:
        row = conn.execute(select(scheduled_payments).where(and_(
            scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id']),
            scheduled_payments.c.enabled == 1
        ))).first()
        if not row: raise ValueError('Обязательный платеж не найден')
        return _create_scheduled_payment_transaction(conn, user, row, wallet_id=wallet_id, category_id=category_id, comment_prefix='Отмечено оплаченным')

def retry_scheduled_payment(user: dict, schedule_id: int, today=None):
    require_permission(user, 'manage_schedules')
    today = today or date.today()
    with engine.begin() as conn:
        row = conn.execute(select(scheduled_payments).where(and_(
            scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id']),
            scheduled_payments.c.enabled == 1
        ))).first()
        if not row: raise ValueError('Автоплатеж не найден')
        m = row._mapping
        if int(m.get('auto_create_expense') or 0) != 1:
            raise ValueError('Автосоздание расхода выключено')
        tx_id = _create_scheduled_payment_transaction(conn, user, row, comment_prefix='Повтор автоплатежа')
        conn.execute(update(scheduled_payments).where(scheduled_payments.c.id == int(schedule_id)).values(last_auto_created_month=today.strftime('%Y-%m')))
        _log(conn, user, 'retry', 'scheduled_payment', int(schedule_id), f'tx={tx_id}')
        return int(tx_id)

def disable_scheduled_payment_auto_create(user: dict, schedule_id: int):
    require_permission(user, 'manage_schedules')
    with engine.begin() as conn:
        row = conn.execute(select(scheduled_payments).where(and_(scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('Автоплатеж не найден')
        conn.execute(update(scheduled_payments).where(scheduled_payments.c.id == int(schedule_id)).values(auto_create_expense=0))
        _log(conn, user, 'disable_auto', 'scheduled_payment', int(schedule_id), row._mapping.get('title'))
        return True



def process_due_scheduled_expenses(today=None):
    """Level 5.5: auto-create expense transactions for recurring mandatory payments."""
    today = today or date.today()
    ym = today.strftime('%Y-%m')
    day = int(today.day)
    created = []
    with engine.begin() as conn:
        rows = conn.execute(select(scheduled_payments, users.c.telegram_id, users.c.full_name)
            .select_from(scheduled_payments.join(users, users.c.id == scheduled_payments.c.user_id))
            .where(and_(scheduled_payments.c.enabled == 1,
                        scheduled_payments.c.auto_create_expense == 1,
                        scheduled_payments.c.due_day <= day,
                        or_(scheduled_payments.c.last_auto_created_month.is_(None), scheduled_payments.c.last_auto_created_month != ym)))).all()
        for r in rows:
            m = r._mapping
            if m.get('last_auto_created_month') == ym:
                continue
            user = {'id': int(m['user_id']), 'telegram_id': int(m['telegram_id']), 'full_name': m.get('full_name') or 'Пользователь', 'family_id': int(m['family_id']), 'role': 'admin'}
            try:
                wallet = _get_wallet(conn, int(m['family_id']), int(m['wallet_id']))
                amount = _d(m['amount'])
                if _d(wallet['balance']) < amount:
                    _log(conn, user, 'skip', 'scheduled_payment', int(m['id']), 'not enough wallet balance for auto expense')
                    continue
                amount_base = _amount_base(int(m['family_id']), amount, m['currency'])
                tx_id = conn.execute(transactions.insert().values(
                    family_id=int(m['family_id']), user_id=int(m['user_id']), type='expense', amount=amount,
                    currency=m['currency'], amount_base=amount_base, wallet_id=int(m['wallet_id']),
                    category_id=int(m['category_id']), transfer_id=None, scheduled_payment_id=int(m['id']),
                    comment=f"Автоплатеж: {m['title']} ({ym})", created_at=_now()
                )).inserted_primary_key[0]
                conn.execute(update(wallets).where(wallets.c.id == int(m['wallet_id'])).values(balance=_d(wallet['balance']) - amount))
                conn.execute(update(scheduled_payments).where(scheduled_payments.c.id == int(m['id'])).values(last_auto_created_month=ym))
                _log(conn, user, 'auto_create', 'scheduled_payment', int(m['id']), f'tx={tx_id}; {amount} {m["currency"]}')
                created.append({'schedule_id': int(m['id']), 'transaction_id': int(tx_id), 'title': m['title'], 'amount': float(amount), 'currency': m['currency']})
            except Exception as exc:
                _log(conn, user, 'error', 'scheduled_payment', int(m['id']), str(exc)[:250])
    return created

def add_financial_plan_item(user: dict, title: str, target_amount: float, currency: str, current_amount: float = 0, priority: int = 3, deadline: str = '', note: str = ''):
    require_permission(user, 'manage_financial_plan')
    title = _clean_text(title, 160)
    if not title: raise ValueError('Название пункта плана обязательно')
    target = _money(target_amount, 'Целевая сумма')
    current = Decimal(str(current_amount or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if current < 0: raise ValueError('Текущая сумма не может быть отрицательной')
    currency = validate_currency(currency)
    priority = max(1, min(5, int(priority or 3)))
    with engine.begin() as conn:
        pid = conn.execute(financial_plan_items.insert().values(
            family_id=int(user['family_id']), user_id=int(user['id']), title=title,
            target_amount=target, current_amount=current, currency=currency, priority=priority,
            deadline=_clean_text(deadline,20), note=_clean_text(note,500), created_at=_now()
        )).inserted_primary_key[0]
        _log(conn, user, 'create', 'financial_plan_item', int(pid), title)
        return int(pid)

def update_financial_plan_item(user: dict, item_id: int, **data):
    require_permission(user, 'manage_financial_plan')
    vals = {}
    if 'title' in data:
        title = _clean_text(data.get('title'),160)
        if not title: raise ValueError('Название пункта плана обязательно')
        vals['title'] = title
    if 'target_amount' in data: vals['target_amount'] = _money(data.get('target_amount'), 'Целевая сумма')
    if 'current_amount' in data:
        cur = Decimal(str(data.get('current_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if cur < 0: raise ValueError('Текущая сумма не может быть отрицательной')
        vals['current_amount'] = cur
    if 'currency' in data: vals['currency'] = validate_currency(data.get('currency'))
    if 'priority' in data: vals['priority'] = max(1, min(5, int(data.get('priority') or 3)))
    if 'deadline' in data: vals['deadline'] = _clean_text(data.get('deadline'),20)
    if 'note' in data: vals['note'] = _clean_text(data.get('note'),500)
    with engine.begin() as conn:
        row = conn.execute(select(financial_plan_items).where(and_(financial_plan_items.c.id == int(item_id), financial_plan_items.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('Пункт финансового плана не найден')
        if vals:
            conn.execute(update(financial_plan_items).where(financial_plan_items.c.id == int(item_id)).values(**vals))
            _log(conn, user, 'edit', 'financial_plan_item', int(item_id), str(vals))
        return True

def delete_financial_plan_item(user: dict, item_id: int):
    require_permission(user, 'manage_financial_plan')
    with engine.begin() as conn:
        row = conn.execute(select(financial_plan_items).where(and_(financial_plan_items.c.id == int(item_id), financial_plan_items.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('Пункт финансового плана не найден')
        conn.execute(delete(financial_plan_items).where(financial_plan_items.c.id == int(item_id)))
        _log(conn, user, 'delete', 'financial_plan_item', int(item_id), row._mapping['title'])
        return True

def get_financial_plan_items(family_id: int):
    with engine.begin() as conn:
        rows = _rows(conn.execute(select(financial_plan_items).where(financial_plan_items.c.family_id == int(family_id)).order_by(financial_plan_items.c.priority, financial_plan_items.c.id)))
    for r in rows:
        target = float(r.get('target_amount') or 0)
        current = float(r.get('current_amount') or 0)
        r['progress_percent'] = round((current / target * 100) if target else 0, 1)
    return rows


# --- Level 5.4: granular permissions, financial calendar, AI-style analysis ---
ALL_FAMILY_PERMISSIONS = sorted({p for perms in ROLE_PERMISSIONS.values() for p in perms} | {
    'manage_family', 'manage_wallets', 'manage_categories', 'manage_rates', 'manage_budget',
    'manage_debt', 'manage_goals', 'manage_schedules', 'manage_financial_plan',
    'add_transaction', 'transfer', 'export', 'view_ai_analysis'
})

def get_effective_permissions(user: dict) -> list[str]:
    return sorted([p for p in ALL_FAMILY_PERMISSIONS if has_permission(user, p)])

def get_member_permissions(admin_user: dict, member_id: int):
    require_permission(admin_user, 'manage_family')
    family_id = int(admin_user['family_id'])
    with engine.begin() as conn:
        member = conn.execute(select(users).where(and_(users.c.id == int(member_id), users.c.family_id == family_id))).first()
        if not member:
            raise ValueError('Участник не найден')
        overrides = conn.execute(select(family_member_permission_overrides).where(and_(
            family_member_permission_overrides.c.family_id == family_id,
            family_member_permission_overrides.c.user_id == int(member_id),
        ))).all()
    base = set(ROLE_PERMISSIONS.get(member._mapping['role'], set()))
    override_map = {r._mapping['permission']: bool(r._mapping['allowed']) for r in overrides}
    effective = sorted([p for p in ALL_FAMILY_PERMISSIONS if override_map.get(p, p in base)])
    return {'member_id': int(member_id), 'role': member._mapping['role'], 'base_permissions': sorted(base), 'overrides': override_map, 'effective_permissions': effective, 'all_permissions': ALL_FAMILY_PERMISSIONS}

def set_member_permissions(admin_user: dict, member_id: int, permissions: list[str]):
    require_permission(admin_user, 'manage_family')
    family_id = int(admin_user['family_id'])
    requested = set(str(p) for p in (permissions or []) if str(p) in ALL_FAMILY_PERMISSIONS)
    with engine.begin() as conn:
        member = conn.execute(select(users).where(and_(users.c.id == int(member_id), users.c.family_id == family_id))).first()
        if not member:
            raise ValueError('Участник не найден')
        if int(member_id) == int(admin_user['id']) and 'manage_family' not in requested:
            raise ValueError('Нельзя забрать manage_family у самого себя')
        base = set(ROLE_PERMISSIONS.get(member._mapping['role'], set()))
        conn.execute(delete(family_member_permission_overrides).where(and_(
            family_member_permission_overrides.c.family_id == family_id,
            family_member_permission_overrides.c.user_id == int(member_id),
        )))
        now = _now()
        rows = []
        for perm in ALL_FAMILY_PERMISSIONS:
            desired = perm in requested
            if desired != (perm in base):
                rows.append({'family_id': family_id, 'user_id': int(member_id), 'permission': perm, 'allowed': 1 if desired else 0, 'updated_at': now})
        if rows:
            conn.execute(family_member_permission_overrides.insert(), rows)
        _log(conn, admin_user, 'edit', 'member_permissions', int(member_id), ','.join(sorted(requested)))
    return get_member_permissions(admin_user, member_id)

def get_financial_calendar(family_id: int, ym=None):
    ym, start, end = _month_range(ym)
    events = []
    with engine.begin() as conn:
        tx_rows = conn.execute(select(transactions, wallets.c.name.label('wallet_name'), categories.c.name.label('category_name'))
            .select_from(transactions.outerjoin(wallets, wallets.c.id == transactions.c.wallet_id).outerjoin(categories, categories.c.id == transactions.c.category_id))
            .where(and_(transactions.c.family_id == int(family_id), transactions.c.created_at >= start, transactions.c.created_at < end))
            .order_by(transactions.c.created_at)).all()
        schedules = conn.execute(select(scheduled_payments).where(and_(scheduled_payments.c.family_id == int(family_id), scheduled_payments.c.enabled == 1)).order_by(scheduled_payments.c.due_day)).all()
    for r in tx_rows:
        m = r._mapping
        events.append({
            'date': m['created_at'].date().isoformat(), 'kind': 'transaction', 'type': m['type'],
            'title': m.get('category_name') or m['type'], 'amount': float(m['amount'] or 0), 'currency': m['currency'],
            'wallet_name': m.get('wallet_name'), 'comment': m.get('comment') or '', 'id': m['id'],
        })
    year, month = map(int, ym.split('-'))
    import calendar as _cal
    last_day = _cal.monthrange(year, month)[1]
    for r in schedules:
        m = r._mapping
        day = min(int(m['due_day'] or 1), last_day)
        events.append({
            'date': f'{ym}-{day:02d}', 'kind': 'scheduled_payment', 'type': m['kind'],
            'title': m['title'], 'amount': float(m['amount'] or 0), 'currency': m['currency'], 'id': m['id'],
            'enabled': bool(m['enabled']),
        })
    events.sort(key=lambda x: (x['date'], 0 if x['kind'] == 'scheduled_payment' else 1))
    days = {}
    for e in events:
        days.setdefault(e['date'], []).append(e)
    import calendar as _calendar
    first_weekday, last_day = _calendar.monthrange(year, month)
    cells = [{'date': None, 'day': '', 'events': [], 'income': 0, 'expense': 0, 'scheduled': 0} for _ in range(first_weekday)]
    for dday in range(1, last_day + 1):
        date_key = f'{ym}-{dday:02d}'
        evs = days.get(date_key, [])
        income = sum(float(e.get('amount') or 0) for e in evs if e.get('type') == 'income')
        expense = sum(float(e.get('amount') or 0) for e in evs if e.get('type') == 'expense')
        scheduled_sum = sum(float(e.get('amount') or 0) for e in evs if e.get('kind') == 'scheduled_payment')
        cells.append({'date': date_key, 'day': dday, 'events': evs, 'income': round(income,2), 'expense': round(expense,2), 'scheduled': round(scheduled_sum,2)})
    while len(cells) % 7:
        cells.append({'date': None, 'day': '', 'events': [], 'income': 0, 'expense': 0, 'scheduled': 0})
    weeks = [cells[i:i+7] for i in range(0, len(cells), 7)]
    return {'month': ym, 'events': events, 'days': [{'date': k, 'events': v} for k, v in days.items()], 'weeks': weeks, 'weekdays': ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']}

def get_ai_monthly_analysis(family_id: int, ym=None):
    ym = validate_month(ym)
    summary = get_month_summary(family_id, ym)
    categories_report = get_expense_by_categories(family_id, ym)
    budgets_report = get_budgets(family_id, ym)
    forecast = get_expense_forecast(family_id)
    income = float(summary.get('income') or 0)
    expense = float(summary.get('expense') or 0)
    balance = float(summary.get('balance') or 0)
    savings_rate = round((balance / income * 100) if income else 0, 1)
    top = categories_report[0] if categories_report else None
    insights = []
    risks = []
    actions = []
    if income <= 0:
        risks.append('В этом месяце пока нет доходов. Отчет по экономии будет точнее после внесения дохода.')
    if expense > income and income > 0:
        risks.append('Расходы выше доходов: месяц идет с отрицательным денежным потоком.')
        actions.append('Заморозить необязательные расходы до следующего дохода и проверить категории с наибольшей долей.')
    elif savings_rate >= 20:
        insights.append(f'Хороший уровень остатка: примерно {savings_rate}% от дохода остается в плюсе.')
    elif income > 0:
        risks.append(f'Остаток низкий: примерно {savings_rate}% от дохода. Желательно целиться хотя бы в 10–20%.')
    if top:
        insights.append(f'Главная категория расходов: {top["category_name"]} — {top["percent"]}% расходов месяца.')
        if float(top.get('percent') or 0) >= 40:
            actions.append(f'Разбей категорию «{top["category_name"]}» на подкатегории, чтобы найти конкретный источник перерасхода.')
    over = [b for b in budgets_report if float(b.get('percent') or 0) >= 100]
    near = [b for b in budgets_report if 80 <= float(b.get('percent') or 0) < 100]
    if over:
        risks.append('Превышены бюджеты: ' + ', '.join(b.get('category_name','') for b in over[:5]))
        actions.append('По превышенным бюджетам поставь стоп-лимит до конца месяца или перенеси лимит осознанно.')
    if near:
        insights.append('Близко к лимиту: ' + ', '.join(b.get('category_name','') for b in near[:5]))
    if forecast.get('projected_expense'):
        insights.append(f"Прогноз расходов к концу месяца: {float(forecast.get('projected_expense') or 0):,.0f}".replace(',', ' '))
    if not actions:
        actions.append('Продолжай ежедневно фиксировать расходы и раз в неделю проверяй топ-3 категории.')
    score = 50
    if income > 0:
        score += min(30, max(-30, savings_rate))
    score -= min(25, len(over) * 8)
    score = max(0, min(100, round(score)))
    return {'month': ym, 'score': score, 'summary': summary, 'top_categories': categories_report[:5], 'insights': insights, 'risks': risks, 'recommended_actions': actions, 'note': 'Это rule-based AI-анализ без отправки данных во внешние AI-сервисы.'}


# --- Level 5.5: recurring expense, mandatory payments, subcategories, AI rules and setup wizard ---

def get_mandatory_payments_month(family_id: int, ym=None, today=None):
    """Return mandatory payments grouped for UX: overdue, upcoming and paid.

    A payment is considered paid only when a transaction has the same
    scheduled_payment_id in the selected month. This avoids fragile comment
    matching and supports both auto-created and manually paid mandatory items.
    """
    ym = validate_month(ym)
    today = today or date.today()
    start, end = _month_range(ym)[1:]
    is_current_month = today.strftime('%Y-%m') == ym
    today_day = int(today.day) if is_current_month else 1
    with engine.begin() as conn:
        schedules = _rows(conn.execute(select(scheduled_payments, wallets.c.name.label('wallet_name'), categories.c.name.label('category_name'))
            .select_from(scheduled_payments.outerjoin(wallets, wallets.c.id == scheduled_payments.c.wallet_id).outerjoin(categories, categories.c.id == scheduled_payments.c.category_id))
            .where(and_(scheduled_payments.c.family_id == int(family_id), scheduled_payments.c.enabled == 1))
            .order_by(scheduled_payments.c.due_day, scheduled_payments.c.id)).all())
        tx_rows = _rows(conn.execute(select(transactions.c.scheduled_payment_id)
            .where(and_(transactions.c.family_id == int(family_id), transactions.c.created_at >= start, transactions.c.created_at < end, transactions.c.scheduled_payment_id.is_not(None)))).all())
    paid_schedule_ids = {int(t.get('scheduled_payment_id')) for t in tx_rows if t.get('scheduled_payment_id')}
    total = 0.0
    rows = []
    overdue, upcoming, paid_items = [], [], []
    for s in schedules:
        sid = int(s.get('id'))
        paid = bool(sid in paid_schedule_ids)
        due_day = int(s.get('due_day') or 1)
        status = 'paid' if paid else ('overdue' if is_current_month and due_day < today_day else 'upcoming')
        total += float(s.get('amount') or 0)
        left = 0 if paid else float(s.get('amount') or 0)
        item = {**s, 'month': ym, 'paid': paid, 'left_amount': left, 'status': status}
        rows.append(item)
        if status == 'paid': paid_items.append(item)
        elif status == 'overdue': overdue.append(item)
        else: upcoming.append(item)
    left_amount = round(sum(x['left_amount'] for x in rows), 2)
    return {
        'month': ym, 'items': rows, 'overdue': overdue, 'upcoming': upcoming, 'paid': paid_items,
        'total_amount': round(total, 2), 'left_amount': left_amount,
        'overdue_amount': round(sum(float(x.get('left_amount') or 0) for x in overdue), 2),
        'upcoming_amount': round(sum(float(x.get('left_amount') or 0) for x in upcoming), 2),
        'paid_count': sum(1 for x in rows if x['paid']), 'total_count': len(rows)
    }



def get_scheduled_payment_issues(family_id: int, limit: int = 50):
    """Return unresolved recent auto-payment/recurring-payment failures for the family."""
    limit = max(1, min(int(limit or 50), 200))
    with engine.begin() as conn:
        rows = conn.execute(select(
            audit_logs.c.id, audit_logs.c.action, audit_logs.c.entity_id.label('schedule_id'),
            audit_logs.c.details, audit_logs.c.resolved_at, audit_logs.c.created_at, scheduled_payments.c.title,
            scheduled_payments.c.amount, scheduled_payments.c.currency, scheduled_payments.c.due_day
        ).select_from(audit_logs.outerjoin(scheduled_payments, scheduled_payments.c.id == audit_logs.c.entity_id))
         .where(and_(audit_logs.c.family_id == int(family_id), audit_logs.c.entity_type == 'scheduled_payment', audit_logs.c.action.in_(['error', 'skip']), audit_logs.c.resolved_at.is_(None)))
         .order_by(audit_logs.c.id.desc()).limit(limit)).all()
    return _rows(rows)


def get_money_until_month_end(family_id: int, ym=None, today=None):
    """Compute how much money remains after unpaid mandatory payments and daily allowance until month end."""
    import calendar as _calendar_l552
    today = today or date.today()
    ym = validate_month(ym or today.strftime('%Y-%m'))
    year, month = [int(x) for x in ym.split('-')]
    if today.strftime('%Y-%m') != ym:
        calc_day = date(year, month, 1)
    else:
        calc_day = today
    last_day = _calendar_l552.monthrange(year, month)[1]
    days_left_including_today = max(1, (date(year, month, last_day) - calc_day).days + 1)
    with engine.begin() as conn:
        wallet_rows = conn.execute(select(wallets).where(wallets.c.family_id == int(family_id))).all()
        wallet_base_total = Decimal('0')
        wallet_items = []
        for wr in wallet_rows:
            w = wr._mapping
            bal = _d(w['balance'])
            bal_base = _amount_base(int(family_id), bal, w['currency'])
            include_free = bool(w.get('include_in_free_money', 1))
            if include_free:
                wallet_base_total += bal_base
            wallet_items.append({'id': int(w['id']), 'name': w['name'], 'currency': w['currency'], 'balance': float(bal), 'balance_base': float(bal_base), 'include_in_free_money': include_free})
        mandatory = get_mandatory_payments_month(int(family_id), ym, today=today)
        unpaid_items = [x for x in mandatory.get('items', []) if not x.get('paid')]
        overdue_items = [x for x in unpaid_items if x.get('status') == 'overdue']
        upcoming_items = [x for x in unpaid_items if x.get('status') != 'overdue']
        # Level 5.5.3: include overdue unpaid mandatory payments too.
        # Previously only future unpaid due days were counted, which overstated free money.
        mandatory_left_base = Decimal('0')
        overdue_left_base = Decimal('0')
        upcoming_left_base = Decimal('0')
        for item in unpaid_items:
            amount_base = _amount_base(int(family_id), _d(item.get('left_amount') or item.get('amount') or 0), item.get('currency') or BASE_CURRENCY)
            mandatory_left_base += amount_base
            if item.get('status') == 'overdue': overdue_left_base += amount_base
            else: upcoming_left_base += amount_base
        # Estimate variable spending pace from current-month non-mandatory expenses.
        month_start, month_end = _month_range(ym)[1:]
        spent_base = conn.execute(select(func.coalesce(func.sum(transactions.c.amount_base), 0)).where(and_(
            transactions.c.family_id == int(family_id), transactions.c.type == 'expense',
            transactions.c.created_at >= month_start, transactions.c.created_at < month_end,
            transactions.c.scheduled_payment_id.is_(None)
        ))).scalar() or 0
        days_elapsed = max(1, calc_day.day if calc_day.strftime('%Y-%m') == ym else 1)
        avg_daily_variable = _d(spent_base) / Decimal(days_elapsed)
        variable_forecast_left_base = avg_daily_variable * Decimal(max(0, days_left_including_today - 1))
        free_after_mandatory = wallet_base_total - mandatory_left_base
        free_after_mandatory_and_variable = free_after_mandatory - variable_forecast_left_base
        daily_allowance = free_after_mandatory_and_variable / Decimal(days_left_including_today) if days_left_including_today else free_after_mandatory_and_variable
    return {
        'month': ym,
        'today': calc_day.isoformat(),
        'base_currency': BASE_CURRENCY,
        'wallet_total_base': float(wallet_base_total),
        'mandatory_left_base': float(mandatory_left_base),
        'overdue_left_base': float(overdue_left_base),
        'upcoming_left_base': float(upcoming_left_base),
        'free_after_mandatory': float(free_after_mandatory),
        'variable_spent_base': float(_d(spent_base)),
        'avg_daily_variable_base': float(avg_daily_variable),
        'variable_forecast_left_base': float(variable_forecast_left_base),
        'free_after_mandatory_and_variable': float(free_after_mandatory_and_variable),
        'days_left': days_left_including_today,
        'daily_allowance': float(daily_allowance),
        'wallets': wallet_items,
        'unpaid_mandatory_items': unpaid_items,
        'overdue_mandatory_items': overdue_items,
        'upcoming_mandatory_items': upcoming_items,
        'recommendations': [
            'Сначала закройте обязательные платежи месяца.',
            'Дневной лимит считайте после обязательных платежей и прогноза переменных расходов.',
            'Если свободный остаток отрицательный — сократите переменные расходы или перенесите необязательные траты.'
        ]
    }

# --- Level 5.5.4: mandatory linked transaction polish ---

def get_linkable_transactions_for_mandatory(user: dict, schedule_id: int, ym=None, limit: int = 30):
    """List existing expense transactions that can be linked to a mandatory payment without double spending."""
    require_permission(user, 'manage_schedules')
    ym = validate_month(ym)
    start, end = _month_range(ym)[1:]
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        sched = conn.execute(select(scheduled_payments).where(and_(
            scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == family_id
        ))).first()
        if not sched:
            raise ValueError('Обязательный платеж не найден')
        sm = sched._mapping
        cond = [
            transactions.c.family_id == family_id,
            transactions.c.type == 'expense',
            transactions.c.created_at >= start,
            transactions.c.created_at < end,
            transactions.c.scheduled_payment_id.is_(None),
        ]
        if sm.get('wallet_id'):
            cond.append(transactions.c.wallet_id == int(sm['wallet_id']))
        if sm.get('category_id'):
            cond.append(transactions.c.category_id == int(sm['category_id']))
        # Amount is intentionally not mandatory because partial/converted payments may exist.
        rows = conn.execute(select(
            transactions.c.id, transactions.c.amount, transactions.c.currency, transactions.c.comment,
            transactions.c.created_at, wallets.c.name.label('wallet_name'), categories.c.name.label('category_name')
        ).select_from(transactions.outerjoin(wallets, wallets.c.id == transactions.c.wallet_id).outerjoin(categories, categories.c.id == transactions.c.category_id))
         .where(and_(*cond)).order_by(transactions.c.created_at.desc(), transactions.c.id.desc()).limit(int(limit))).all()
    return _rows(rows)


def link_existing_transaction_to_mandatory(user: dict, schedule_id: int, transaction_id: int, ym=None):
    """Mark a mandatory payment as paid by linking an already-created expense transaction.

    This does not change wallet balance and therefore prevents double spending.
    """
    require_permission(user, 'manage_schedules')
    ym = validate_month(ym)
    start, end = _month_range(ym)[1:]
    family_id = int(user['family_id'])
    with engine.begin() as conn:
        sched = conn.execute(select(scheduled_payments).where(and_(
            scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == family_id,
            scheduled_payments.c.enabled == 1
        ))).first()
        if not sched:
            raise ValueError('Обязательный платеж не найден')
        existing = conn.execute(select(transactions.c.id).where(and_(
            transactions.c.family_id == family_id,
            transactions.c.scheduled_payment_id == int(schedule_id),
            transactions.c.created_at >= start,
            transactions.c.created_at < end,
        ))).first()
        if existing:
            raise ValueError('Этот обязательный платеж уже отмечен оплаченным в этом месяце')
        tx = conn.execute(select(transactions).where(and_(
            transactions.c.id == int(transaction_id), transactions.c.family_id == family_id,
            transactions.c.created_at >= start, transactions.c.created_at < end,
        ))).first()
        if not tx:
            raise ValueError('Операция не найдена в выбранном месяце')
        t = tx._mapping
        if t.get('type') != 'expense':
            raise ValueError('К обязательному платежу можно привязать только расход')
        if t.get('scheduled_payment_id'):
            raise ValueError('Эта операция уже привязана к обязательному платежу')
        conn.execute(update(transactions).where(transactions.c.id == int(transaction_id)).values(scheduled_payment_id=int(schedule_id)))
        _log(conn, user, 'link', 'scheduled_payment', int(schedule_id), f'linked_existing_tx={int(transaction_id)}; no balance change')
        return int(transaction_id)


def mark_mandatory_payment_paid(user: dict, schedule_id: int, wallet_id=None, category_id=None, transaction_id=None, zero_note: bool = False):
    """Mark payment paid without accidental duplicate spending.

    - transaction_id links an existing expense and does not touch balance.
    - zero_note creates a zero amount service expense linked to the schedule.
    - fallback keeps compatibility and creates a real expense only when explicit wallet/category are provided.
    """
    require_permission(user, 'manage_schedules')
    if transaction_id:
        return link_existing_transaction_to_mandatory(user, schedule_id, int(transaction_id), date.today().strftime('%Y-%m'))
    if zero_note:
        with engine.begin() as conn:
            row = conn.execute(select(scheduled_payments).where(and_(
                scheduled_payments.c.id == int(schedule_id), scheduled_payments.c.family_id == int(user['family_id']), scheduled_payments.c.enabled == 1
            ))).first()
            if not row: raise ValueError('Обязательный платеж не найден')
            m = row._mapping
            ym = date.today().strftime('%Y-%m')
            start, end = _month_range(ym)[1:]
            existing = conn.execute(select(transactions.c.id).where(and_(transactions.c.family_id == int(user['family_id']), transactions.c.scheduled_payment_id == int(schedule_id), transactions.c.created_at >= start, transactions.c.created_at < end))).first()
            if existing: raise ValueError('Этот обязательный платеж уже отмечен оплаченным в этом месяце')
            wid = int(wallet_id or m.get('wallet_id') or 0)
            cid = int(category_id or m.get('category_id') or 0)
            if not wid or not cid: raise ValueError('Для служебной отметки выберите кошелек и категорию')
            wallet = _get_wallet(conn, int(user['family_id']), wid)
            if not family_owns_category(int(user['family_id']), cid, 'expense'):
                raise ValueError('Категория расхода не найдена')
            tx_id = conn.execute(transactions.insert().values(
                family_id=int(user['family_id']), user_id=int(user['id']), type='expense', amount=Decimal('0.00'),
                currency=wallet['currency'], amount_base=Decimal('0.00'), wallet_id=wid, category_id=cid,
                transfer_id=None, scheduled_payment_id=int(schedule_id), comment=f'Служебная отметка оплаты: {m.get("title")} ({ym})', created_at=_now()
            )).inserted_primary_key[0]
            _log(conn, user, 'mark_paid', 'scheduled_payment', int(schedule_id), f'zero_service_tx={tx_id}; no balance change')
            return int(tx_id)
    return pay_mandatory_payment(user, schedule_id, wallet_id=wallet_id, category_id=category_id)


def resolve_scheduled_payment_issue(user: dict, issue_id: int):
    require_permission(user, 'manage_schedules')
    with engine.begin() as conn:
        row = conn.execute(select(audit_logs).where(and_(audit_logs.c.id == int(issue_id), audit_logs.c.family_id == int(user['family_id']), audit_logs.c.entity_type == 'scheduled_payment'))).first()
        if not row: raise ValueError('Ошибка автоплатежа не найдена')
        conn.execute(update(audit_logs).where(audit_logs.c.id == int(issue_id)).values(resolved_at=_now()))
        _log(conn, user, 'resolve', 'scheduled_payment_issue', int(issue_id), 'resolved from WebApp')
        return True


def add_ai_personal_rule(user: dict, title: str, rule_type='category_limit', category_id=None, threshold_amount=0, currency=None, enabled=True):
    require_permission(user, 'manage_ai_rules')
    title = _clean_text(title, 160)
    if not title: raise ValueError('Название правила обязательно')
    currency = validate_currency(currency or BASE_CURRENCY)
    amount = Decimal(str(threshold_amount or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount < 0: raise ValueError('Порог не может быть отрицательным')
    category_id = int(category_id) if category_id else None
    if category_id and not family_owns_category(int(user['family_id']), category_id):
        raise ValueError('Категория не найдена')
    with engine.begin() as conn:
        rid = conn.execute(ai_personal_rules.insert().values(family_id=int(user['family_id']), user_id=int(user['id']), title=title, rule_type=_clean_text(rule_type, 40) or 'category_limit', category_id=category_id, threshold_amount=amount, currency=currency, enabled=1 if enabled else 0, created_at=_now())).inserted_primary_key[0]
        _log(conn, user, 'create', 'ai_personal_rule', int(rid), title)
        return int(rid)

def update_ai_personal_rule(user: dict, rule_id: int, **data):
    require_permission(user, 'manage_ai_rules')
    vals = {}
    if 'title' in data: vals['title'] = _clean_text(data.get('title'),160)
    if 'rule_type' in data: vals['rule_type'] = _clean_text(data.get('rule_type'),40) or 'category_limit'
    if 'category_id' in data: vals['category_id'] = int(data.get('category_id')) if data.get('category_id') else None
    if 'threshold_amount' in data: vals['threshold_amount'] = Decimal(str(data.get('threshold_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if 'currency' in data: vals['currency'] = validate_currency(data.get('currency'))
    if 'enabled' in data: vals['enabled'] = 1 if str(data.get('enabled')).lower() in {'1','true','yes','on'} else 0
    with engine.begin() as conn:
        row = conn.execute(select(ai_personal_rules).where(and_(ai_personal_rules.c.id == int(rule_id), ai_personal_rules.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('AI-правило не найдено')
        if vals:
            conn.execute(update(ai_personal_rules).where(ai_personal_rules.c.id == int(rule_id)).values(**vals))
            _log(conn, user, 'edit', 'ai_personal_rule', int(rule_id), str(vals))
        return True

def delete_ai_personal_rule(user: dict, rule_id: int):
    require_permission(user, 'manage_ai_rules')
    with engine.begin() as conn:
        row = conn.execute(select(ai_personal_rules).where(and_(ai_personal_rules.c.id == int(rule_id), ai_personal_rules.c.family_id == int(user['family_id'])))).first()
        if not row: raise ValueError('AI-правило не найдено')
        conn.execute(delete(ai_personal_rules).where(ai_personal_rules.c.id == int(rule_id)))
        _log(conn, user, 'delete', 'ai_personal_rule', int(rule_id), row._mapping['title'])
        return True

def get_ai_personal_rules(family_id: int):
    with engine.begin() as conn:
        rows = conn.execute(select(ai_personal_rules, categories.c.name.label('category_name')).select_from(ai_personal_rules.outerjoin(categories, categories.c.id == ai_personal_rules.c.category_id)).where(ai_personal_rules.c.family_id == int(family_id)).order_by(ai_personal_rules.c.id.desc())).all()
    return _rows(rows)

def get_ai_monthly_analysis_with_rules(user: dict, ym=None):
    analysis = get_ai_monthly_analysis(int(user['family_id']), ym)
    rules = get_ai_personal_rules(int(user['family_id']))
    triggered = []
    cats = {str(c.get('category_id')): c for c in analysis.get('top_categories', [])}
    for r in rules:
        if not r.get('enabled'): continue
        if r.get('rule_type') == 'category_limit' and r.get('category_id'):
            cat = cats.get(str(r.get('category_id')))
            if cat and float(cat.get('amount') or 0) > float(r.get('threshold_amount') or 0):
                triggered.append(f"Правило «{r['title']}»: категория {r.get('category_name') or ''} выше лимита {float(r.get('threshold_amount') or 0):,.0f} {r.get('currency')}")
        elif r.get('rule_type') == 'expense_limit':
            if float(analysis.get('summary',{}).get('expense') or 0) > float(r.get('threshold_amount') or 0):
                triggered.append(f"Правило «{r['title']}»: общие расходы выше лимита {float(r.get('threshold_amount') or 0):,.0f} {r.get('currency')}")
    if triggered:
        analysis['risks'] = (analysis.get('risks') or []) + triggered
        analysis['recommended_actions'] = (analysis.get('recommended_actions') or []) + ['Проверь персональные AI-правила и скорректируй лимиты/расходы.']
    analysis['personal_rules'] = rules
    analysis['triggered_personal_rules'] = triggered
    return analysis

def save_budget_wizard_profile(user: dict, data: dict):
    require_permission(user, 'manage_budget')
    vals = {
        'monthly_income': Decimal(str(data.get('monthly_income') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'base_currency': validate_currency(data.get('base_currency') or BASE_CURRENCY),
        'rent_amount': Decimal(str(data.get('rent_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'kindergarten_amount': Decimal(str(data.get('kindergarten_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'installment_amount': Decimal(str(data.get('installment_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'food_amount': Decimal(str(data.get('food_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'transport_amount': Decimal(str(data.get('transport_amount') or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'savings_target_percent': max(0, min(90, int(data.get('savings_target_percent') or 10))),
        'updated_at': _now(),
    }
    with engine.begin() as conn:
        row = conn.execute(select(budget_wizard_profiles.c.id).where(budget_wizard_profiles.c.family_id == int(user['family_id']))).first()
        if row:
            conn.execute(update(budget_wizard_profiles).where(budget_wizard_profiles.c.id == row._mapping['id']).values(**vals))
            pid = int(row._mapping['id'])
        else:
            pid = conn.execute(budget_wizard_profiles.insert().values(family_id=int(user['family_id']), user_id=int(user['id']), **vals)).inserted_primary_key[0]
        _log(conn, user, 'save', 'budget_wizard', int(pid), 'profile')
    return get_budget_wizard_profile(int(user['family_id']))

def get_budget_wizard_profile(family_id: int):
    with engine.begin() as conn:
        row = conn.execute(select(budget_wizard_profiles).where(budget_wizard_profiles.c.family_id == int(family_id)).order_by(budget_wizard_profiles.c.id.desc())).first()
    profile = _row(row) if row else None
    if not profile:
        return {'profile': None, 'recommendations': []}
    income = float(profile.get('monthly_income') or 0)
    required = sum(float(profile.get(k) or 0) for k in ['rent_amount','kindergarten_amount','installment_amount','food_amount','transport_amount'])
    savings = income * float(profile.get('savings_target_percent') or 0) / 100
    free = income - required - savings
    recs = [
        {'title': 'Обязательные платежи', 'amount': round(required,2), 'note': 'Аренда/садик/рассрочка/еда/транспорт'},
        {'title': 'Цель накоплений', 'amount': round(savings,2), 'note': f"{profile.get('savings_target_percent')}% от дохода"},
        {'title': 'Свободный остаток', 'amount': round(free,2), 'note': 'Можно распределить на долги, инвестиции и прочее'},
    ]
    return {'profile': profile, 'recommendations': recs}
