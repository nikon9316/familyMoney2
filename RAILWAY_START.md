# Railway deploy — Family Finance Level 5.5.4

## Required Railway variables

```env
APP_ENV=production
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_id
BASE_PUBLIC_URL=https://your-project.up.railway.app
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME
ADMIN_PANEL_TOKEN=change_this_secret
SUPERADMIN_TOKEN=change_this_super_secret
SUPERADMIN_TELEGRAM_ID=your_telegram_id
BASE_CURRENCY=UZS
SESSION_COOKIE_SECURE=true
```

## Optional variables

```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
BACKUP_STORAGE_PROVIDER=local
BACKUP_AT_STARTUP=false
BACKUP_EVERY_HOURS=24
BACKUP_KEEP_DAYS=14
REMINDER_ENABLED=true
REMINDER_HOUR=21
REMINDER_MINUTE=0
```

For S3/R2 backups:

```env
BACKUP_STORAGE_PROVIDER=s3
BACKUP_S3_BUCKET=your_bucket
BACKUP_S3_PREFIX=family-finance/backups
BACKUP_S3_ENDPOINT_URL=https://...
BACKUP_S3_REGION=auto
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

## Railway start command

Already configured in `railway.json`:

```bash
alembic upgrade head && python main.py
```

## Healthcheck

Railway checks:

```text
/healthz
```

## After deploy

Open your bot in Telegram and run:

```text
/start
```

Then open the WebApp button from Telegram.
