#!/usr/bin/env python3
"""Production startup smoke check for Railway/PostgreSQL deployments.

Checks:
1) alembic upgrade head;
2) init_db;
3) /healthz;
4) scheduled worker one-shot with a fake bot.
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from aiohttp.test_utils import TestClient, TestServer

async def main() -> int:
    database_url = os.getenv('DATABASE_URL', '')
    print('1/4 alembic upgrade head')
    if database_url.startswith('postgresql'):
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True, cwd=PROJECT_ROOT)
    else:
        print('SQLite/local mode detected: skipping Alembic upgrade. Full Railway check runs this step on PostgreSQL.')

    print('2/4 init_db')
    import database.db as db
    db.init_db()

    print('3/4 healthz')
    import server
    client = TestClient(TestServer(server.create_web_app()))
    await client.start_server()
    try:
      resp = await client.get('/healthz')
      body = await resp.json()
      if resp.status != 200 or not body.get('ok'):
          raise RuntimeError(f'healthz failed: status={resp.status}, body={body}')
    finally:
      await client.close()

    print('4/4 scheduled worker one-shot')
    import scheduled_worker as app_main
    class FakeBot:
        async def send_message(self, telegram_id, text):
            return {'ok': True, 'telegram_id': telegram_id, 'text': text}
    await app_main.check_scheduled_payments_once(FakeBot())
    print('PRODUCTION_STARTUP_CHECK_OK')
    return 0

if __name__ == '__main__':
    if not os.getenv('BOT_TOKEN'):
        os.environ['BOT_TOKEN'] = '123456:TEST_TOKEN'
    raise SystemExit(asyncio.run(main()))
