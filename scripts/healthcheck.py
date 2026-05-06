from database.schema import engine
from sqlalchemy import text

if __name__ == '__main__':
    with engine.begin() as conn:
        conn.execute(text('SELECT 1'))
    print('ok')
