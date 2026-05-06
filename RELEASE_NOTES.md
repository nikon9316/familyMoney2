
## Level 5.4.1

- Fixed offline queued mutations: no premature `loadData()` until network sync.
- Cached last `/api/init` in IndexedDB for offline startup.
- Added offline sync conflicts UI.
- Protected AI analysis from `/api/init` for users without `view_ai_analysis`.
- Centralized family permission matrix and added UI hiding by permissions.
- Added Level 5.4.1 tests.

# Release Notes — Level 4.6.1

## Тип релиза

Технический чистый релиз без изменения бизнес-логики.

## Изменения

1. Удалены служебные директории `.pytest_cache` и `__pycache__`.
2. Удалены тестовые базы данных из архива.
3. Исправлен заголовок WebApp: `Family Finance 4.6`.
4. Старые README перенесены в `docs/`.
5. В корне оставлены актуальные файлы релиза: `README_LEVEL4_6_1.md`, `RELEASE_NOTES.md`, deployment/checklist файлы.

## Не изменялось

- Финансовая логика.
- API.
- Alembic-миграции.
- WebApp-функциональность.
- Админ-панель.

## Рекомендованный следующий шаг

Level 4.7 — настоящий поэтапный рефакторинг `database/monolith.py` в доменные модули.


## Level 4.7 — DB refactor
- Moved SQLAlchemy table definitions from `database/monolith.py` to `database/schema.py`.
- Converted `database/monolith.py` into a deprecated compatibility shim.
- Added `database/core.py` as temporary legacy implementation core.
- Updated domain modules to stop importing from `database.monolith`.
- Kept `database/db.py` as public facade for backward-compatible imports.


## Level 5.0 — production preparation

- Railway/PostgreSQL deployment checklist and production env variables.
- `/healthz` endpoint for monitoring.
- Optional Sentry integration via `SENTRY_DSN`.
- Telegram admin error notifications can be disabled with `ERROR_NOTIFY_TELEGRAM=false`.
- Privacy policy page at `/privacy`.
- Scheduled backups with startup/interval options and `scripts/backup_once.py`.
- Production UI polish for WebApp.
- Real Chart.js CDN integration with offline fallback.
