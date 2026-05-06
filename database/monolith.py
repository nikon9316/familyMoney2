"""Deprecated compatibility module for Level 4.7.

The database layer is now accessed through database/db.py and domain modules.
This file intentionally contains no table definitions or business implementation.
It re-exports the facade only so very old imports keep working during migration.
"""
from database.db import *  # noqa: F401,F403
