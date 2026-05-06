import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from app_logging import setup_logging
from backup import create_backup, cleanup_old_backups
from config import BOT_TOKEN, WEB_HOST, WEB_PORT, REMINDER_ENABLED, REMINDER_HOUR, REMINDER_MINUTE, BACKUP_ENABLED, BACKUP_HOUR, BACKUP_AT_STARTUP, BACKUP_EVERY_HOURS
from bot.handlers import router
from database.db import init_db, get_users_for_reminders, get_month_summary
from server import create_web_app
from scheduled_worker import check_scheduled_payments_once

logger = setup_logging()

async def start_web_server():
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_HOST, WEB_PORT)
    await site.start()
    logger.info('WebApp started on http://%s:%s', WEB_HOST, WEB_PORT)

async def reminder_worker(bot: Bot):
    if not REMINDER_ENABLED:
        logger.info('Daily reminders disabled')
        return
    while True:
        now = datetime.now()
        target = now.replace(hour=REMINDER_HOUR, minute=REMINDER_MINUTE, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        for u in get_users_for_reminders():
            try:
                m = get_month_summary(u['family_id'])
                text = (
                    '⏰ Напоминание: не забудьте внести расходы за сегодня.\n\n'
                    f"За месяц:\nДоход: {m['income']:,.0f}\nРасход: {m['expense']:,.0f}\nОстаток: {m['balance']:,.0f}"
                ).replace(',', ' ')
                await bot.send_message(u['telegram_id'], text)
            except Exception:
                logger.exception('Reminder error for user=%s', u.get('telegram_id'))


async def scheduled_payments_worker(bot: Bot):
    """Level 5.3.1: check planned payments immediately at startup, then hourly."""
    if not REMINDER_ENABLED:
        logger.info('Scheduled payment reminders disabled with REMINDER_ENABLED=false')
        return
    await check_scheduled_payments_once(bot)
    while True:
        await asyncio.sleep(60 * 60)
        await check_scheduled_payments_once(bot)

async def backup_worker():
    if not BACKUP_ENABLED:
        logger.info('Backups disabled')
        return
    if BACKUP_AT_STARTUP:
        try:
            path = create_backup()
            deleted = cleanup_old_backups()
            logger.info('Startup backup created: %s; old deleted=%s', path, deleted)
        except Exception:
            logger.exception('Startup backup failed')
    while True:
        now = datetime.now()
        target = now.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        # Optional extra safety: if BACKUP_EVERY_HOURS is lower than 24, run more often.
        sleep_seconds = (target - now).total_seconds()
        if BACKUP_EVERY_HOURS and BACKUP_EVERY_HOURS < 24:
            sleep_seconds = min(sleep_seconds, BACKUP_EVERY_HOURS * 3600)
        await asyncio.sleep(sleep_seconds)
        try:
            path = create_backup()
            deleted = cleanup_old_backups()
            logger.info('Automatic backup created: %s; old deleted=%s', path, deleted)
        except Exception:
            logger.exception('Automatic backup failed')

async def main():
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN не найден. Добавь его в .env')
    init_db()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher()
    dp.include_router(router)
    await start_web_server()
    asyncio.create_task(reminder_worker(bot))
    asyncio.create_task(backup_worker())
    asyncio.create_task(scheduled_payments_worker(bot))
    logger.info('Bot started')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
