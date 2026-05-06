"""Database initialization and compatibility migrations."""
from database.core import init_db, ensure_level4_3_tables
__all__ = [name for name in globals() if not name.startswith('__')]
