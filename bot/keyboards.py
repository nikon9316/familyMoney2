from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config import WEBAPP_URL


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть WebApp", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="📊 Баланс", callback_data="balance")],
        [InlineKeyboardButton(text="➕ Доход", callback_data="add_income"), InlineKeyboardButton(text="➖ Расход", callback_data="add_expense")],
    ])
