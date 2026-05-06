from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from database.db import (
    get_or_create_user, get_summary, get_family, get_members, get_wallets,
    get_categories, add_transaction, get_category_id_by_name, get_recent_transactions,
)
from bot.keyboards import main_menu

router = Router()

def fmt(n): return f"{float(n or 0):,.0f}".replace(',', ' ')

def _help_quick(kind: str, wallets, cats):
    cmd = '/income' if kind == 'income' else '/expense'
    example_cat = cats[0]['name'] if cats else ('Зарплата' if kind == 'income' else 'Продукты')
    wallet = wallets[0]['name'] if wallets else 'Наличные'
    cat_lines = ', '.join(c['name'] for c in cats[:8]) or 'нет категорий'
    wallet_lines = ', '.join(w['name'] for w in wallets[:8]) or 'нет кошельков'
    return (
        f"Формат:\n<code>{cmd} сумма категория | кошелек | комментарий</code>\n\n"
        f"Пример:\n<code>{cmd} 120000 {example_cat} | {wallet} | обед</code>\n\n"
        f"Категории: {cat_lines}\nКошельки: {wallet_lines}"
    )

def _find_wallet(wallets, name):
    name = (name or '').strip().lower()
    if not name and wallets:
        return wallets[0]
    for w in wallets:
        if str(w['name']).lower() == name:
            return w
    for w in wallets:
        if name in str(w['name']).lower():
            return w
    return None

def _find_category(categories, name):
    """Level 5.5.4: tolerant category search for Telegram quick commands."""
    name = (name or '').strip().lower()
    for c in categories:
        if str(c['name']).lower() == name:
            return c
    for c in categories:
        cname = str(c['name']).lower()
        if name and (name in cname or cname in name):
            return c
    return None

def _parse_quick(text: str):
    # /expense 120000 Продукты | Наличные | обед
    parts = (text or '').split(maxsplit=2)
    if len(parts) < 3:
        return None
    amount = parts[1]
    tail = parts[2]
    chunks = [x.strip() for x in tail.split('|')]
    category = chunks[0]
    wallet = chunks[1] if len(chunks) > 1 else ''
    comment = chunks[2] if len(chunks) > 2 else ''
    return amount, category, wallet, comment

@router.message(CommandStart())
async def start(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name or 'Без имени')
    family = get_family(user['family_id'])
    await message.answer(
        "👨‍👩‍👧 <b>Family Finance Level 5.5.4</b>\n\n"
        "Production hardening версия перед запуском: WebApp, семейные роли, валюты, цели, бюджеты, графики, Excel/PDF, backup, мониторинг и быстрый учет через Telegram.\n\n"
        f"Код приглашения семьи: <code>{family['invite_code']}</code>\n"
        "Команды: /balance, /income, /expense, /last, /invite, /menu",
        reply_markup=main_menu()
    )

@router.message(Command('menu'))
async def menu(message: Message):
    await message.answer('Главное меню:', reply_markup=main_menu())

@router.message(Command('invite'))
async def invite(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name or 'Без имени')
    family = get_family(user['family_id'])
    members = get_members(user['family_id'])
    names = '\n'.join([f"• {m['full_name']} — {m['role']}" for m in members])
    await message.answer(f"👨‍👩‍👧 <b>Семья</b>\n\nКод приглашения: <code>{family['invite_code']}</code>\n\nУчастники:\n{names}")

@router.message(Command('balance'))
async def balance_command(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name or 'Без имени')
    summary = get_summary(user['family_id'])
    await message.answer(_balance_text(summary))

def _balance_text(summary):
    return (
        "📊 <b>Баланс семьи</b>\n\n"
        f"Доходы: {fmt(summary['income'])} {summary['base_currency']}\n"
        f"Расходы: {fmt(summary['expense'])} {summary['base_currency']}\n"
        f"Остаток: {fmt(summary['balance'])} {summary['base_currency']}\n"
        f"Долги осталось: {fmt(summary['debt_left'])} {summary['base_currency']}"
    )

@router.message(Command('last'))
async def last_operations(message: Message):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name or 'Без имени')
    rows = get_recent_transactions(user['family_id'], limit=5)
    if not rows:
        await message.answer('Операций пока нет.')
        return
    text = '<b>Последние операции</b>\n\n' + '\n'.join(
        f"• {'+' if r['type'] in ('income','transfer_in') else '-'} {fmt(r['amount'])} {r['currency']} — {r.get('category_name') or r['type']} / {r.get('wallet_name') or ''}"
        for r in rows
    )
    await message.answer(text)

async def _quick_tx(message: Message, tx_type: str):
    user = get_or_create_user(message.from_user.id, message.from_user.full_name or 'Без имени')
    wallets = get_wallets(user['family_id'])
    cats = get_categories(user['family_id'], tx_type)
    parsed = _parse_quick(message.text or '')
    if not parsed:
        await message.answer(_help_quick(tx_type, wallets, cats))
        return
    amount, category_name, wallet_name, comment = parsed
    wallet = _find_wallet(wallets, wallet_name)
    if not wallet:
        await message.answer('Кошелек не найден.\n\n' + _help_quick(tx_type, wallets, cats))
        return
    try:
        category = _find_category(cats, category_name)
        if not category:
            category_id = get_category_id_by_name(user['family_id'], category_name, tx_type)
            category_label = category_name
        else:
            category_id = category['id']
            category_label = category['name']
        tx_id = add_transaction(user, tx_type, amount, wallet['currency'], wallet['id'], category_id, comment)
        await message.answer(f"✅ {'Доход' if tx_type=='income' else 'Расход'} сохранен: #{tx_id}\n{fmt(amount)} {wallet['currency']} · {category_label} · {wallet['name']}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}\n\n" + _help_quick(tx_type, wallets, cats))

@router.message(Command('expense'))
async def quick_expense(message: Message):
    await _quick_tx(message, 'expense')

@router.message(Command('income'))
async def quick_income(message: Message):
    await _quick_tx(message, 'income')

@router.callback_query(F.data == 'balance')
async def balance(callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id, callback.from_user.full_name or 'Без имени')
    summary = get_summary(user['family_id'])
    await callback.message.answer(_balance_text(summary))
    await callback.answer()

@router.callback_query(F.data.in_({'add_income', 'add_expense'}))
async def open_webapp_hint(callback: CallbackQuery):
    await callback.message.answer('Добавление операций можно делать через WebApp или командами /income и /expense 👇', reply_markup=main_menu())
    await callback.answer()
