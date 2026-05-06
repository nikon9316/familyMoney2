# Railway Deployment Checklist — Family Finance Level 4.4.1

## 1. Подготовить Railway

1. Создать Railway project.
2. Добавить PostgreSQL plugin.
3. Скопировать `DATABASE_URL` из PostgreSQL variables в сервис приложения.
4. Добавить домен Railway или свой домен.

## 2. Environment variables

Минимум:

```env
BOT_TOKEN=123456:telegram_token
BASE_PUBLIC_URL=https://your-service.up.railway.app
DATABASE_URL=${{Postgres.DATABASE_URL}}
ENVIRONMENT=production
RUN_MIGRATIONS_ON_START=true
SESSION_COOKIE_SECURE=true
ADMIN_PANEL_TOKEN=generate_48_chars
SUPERADMIN_TOKEN=generate_48_chars
ADMIN_IP_ALLOWLIST=
BACKUP_DIR=backups
```

Дополнительно для PDF:

```env
PDF_REPORT_FONT=DejaVuSans
PDF_REPORT_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
PDF_REPORT_FONT_BOLD_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
```

## 3. Build

Проект содержит `Dockerfile`, который устанавливает:

- Python dependencies;
- `postgresql-client` для `pg_dump`/`psql`;
- DejaVu fonts для PDF с кириллицей.

## 4. Start command

В Railway Settings → Deploy → Start Command:

```bash
alembic upgrade head && python main.py
```

## 5. Smoke-test после деплоя

Открыть:

```text
https://your-service.up.railway.app/
https://your-service.up.railway.app/admin
```

Проверить через Telegram:

1. `/start`
2. открыть WebApp;
3. добавить кошелек;
4. добавить доход;
5. добавить расход;
6. открыть отчеты;
7. скачать PDF;
8. проверить backup в админке.

## 6. Проверка миграций вручную

Локально или в Railway shell:

```bash
alembic current
alembic upgrade head
```

Ожидаемая версия:

```text
0008_level4_3_2_numeric_cleanup
```

## 7. Security checklist

- `ADMIN_PANEL_TOKEN` не должен быть `change-me`.
- `SUPERADMIN_TOKEN` должен отличаться от admin token.
- Включить `SESSION_COOKIE_SECURE=true`.
- Желательно указать `ADMIN_IP_ALLOWLIST`.
- Проверить, что restore работает только в maintenance mode и требует OTP.
- Периодически скачивать backup.

## 8. Backup checklist

Перед restore система делает автоматический backup. Но в продакшене также желательно:

- включить Railway PostgreSQL backups;
- хранить копии вне Railway;
- не делать restore без теста на отдельной базе.
