import logging
from datetime import datetime

from database.db import get_due_scheduled_payments, log_scheduled_payment_delivery, process_due_scheduled_expenses

logger = logging.getLogger('family_finance.scheduled_worker')


async def check_scheduled_payments_once(bot):
    """Send due planned-payment reminders and auto-create recurring expenses once."""
    try:
        created = process_due_scheduled_expenses()
        if created:
            logger.info('Auto-created scheduled expenses: %s', len(created))
    except Exception:
        logger.exception('Scheduled auto-expense processing failed')

    ym = datetime.now().strftime('%Y-%m')
    for item in get_due_scheduled_payments():
        sid = int(item['id'])
        recipient_user_id = int(item.get('recipient_user_id') or item.get('user_id') or 0)
        telegram_id = int(item['telegram_id'])
        family_id = int(item['family_id'])
        try:
            text = (
                '🔔 Напоминание о платеже\n\n'
                f"{item['title']}\n"
                f"Сумма: {float(item.get('amount') or 0):,.0f} {item.get('currency','')}\n"
                f"День месяца: {item.get('due_day')}"
            ).replace(',', ' ')
            await bot.send_message(telegram_id, text)
            log_scheduled_payment_delivery(sid, recipient_user_id, telegram_id, family_id, ym, status='sent')
        except Exception as exc:
            log_scheduled_payment_delivery(sid, recipient_user_id, telegram_id, family_id, ym, status='error', error=str(exc)[:500])
            logger.exception('Scheduled payment reminder error schedule=%s user=%s', sid, telegram_id)
