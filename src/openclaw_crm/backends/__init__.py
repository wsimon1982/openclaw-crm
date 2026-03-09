"""Storage backends for openclaw-crm."""
from __future__ import annotations

from openclaw_crm.sheets import SheetsBackend, SheetResult  # noqa: F401

try:
    from openclaw_crm.backends.gspread_backend import GspreadBackend  # noqa: F401
except ImportError:
    pass

__all__ = ["SheetsBackend", "SheetResult"]
