"""Compatibility facade for database layer.

Level 4.6 splits the previous large `database/db.py` into smaller modules.
Existing imports (`from database.db import ...`) continue to work because this
facade re-exports the public API from the domain modules.
"""
from database.schema import *  # noqa: F401,F403
from database.users import *  # noqa: F401,F403
from database.wallets import *  # noqa: F401,F403
from database.categories import *  # noqa: F401,F403
from database.transactions import *  # noqa: F401,F403
from database.transfers import *  # noqa: F401,F403
from database.debts import *  # noqa: F401,F403
from database.goals import *  # noqa: F401,F403
from database.budgets import *  # noqa: F401,F403
from database.reports import *  # noqa: F401,F403
from database.admin import *  # noqa: F401,F403
from database.audit import *  # noqa: F401,F403
from database.sessions import *  # noqa: F401,F403
from database.notifications import *  # noqa: F401,F403
from database.integrity import *  # noqa: F401,F403
from database.lifecycle import *  # noqa: F401,F403

from database.financial_plan import *  # noqa: F401,F403
