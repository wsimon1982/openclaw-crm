"""GspreadBackend — Google Sheets backend using the gspread library.

Installation
------------
pip install "openclaw-crm[gspread]"

Quick start
-----------
>>> import gspread
>>> from openclaw_crm.backends.gspread_backend import GspreadBackend
>>> from openclaw_crm.sheets import set_backend
>>>
>>> # Authenticate via a service-account JSON key file
>>> gc = gspread.service_account(filename="service_account.json")
>>> set_backend(GspreadBackend(gc))
>>>
>>> # Or use Application Default Credentials (gcloud auth application-default login)
>>> gc = gspread.auth.local_server_flow(scopes=gspread.auth.READONLY_SCOPES)
>>> set_backend(GspreadBackend(gc))

All read/append/update calls in the rest of the application then go through
the gspread library rather than the ``gws`` CLI.
"""

from __future__ import annotations

from typing import Any

try:
    import gspread  # type: ignore
    from gspread.exceptions import APIError, SpreadsheetNotFound  # type: ignore
except ImportError as _exc:
    raise ImportError(
        "The 'gspread' package is required for GspreadBackend. "
        "Install it with: pip install 'openclaw-crm[gspread]'"
    ) from _exc

from openclaw_crm.sheets import SheetsBackend, SheetResult


class GspreadBackend(SheetsBackend):
    """Sheets backend backed by the `gspread` Python library.

    Parameters
    ----------
    client:
        An authenticated :class:`gspread.Client` instance.  Create one with
        ``gspread.service_account()``, ``gspread.oauth()``, or any other
        gspread auth helper.
    """

    def __init__(self, client: "gspread.Client") -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _open_sheet(self, spreadsheet_id: str, range_: str) -> tuple[Any, str]:
        """Return (worksheet, bare_range) from a spreadsheet_id and A1 range.

        ``range_`` may optionally be prefixed with a sheet name separated by
        ``!``, e.g. ``"Pipeline!A1:Z"``.  When no ``!`` is present the first
        worksheet is used.
        """
        spreadsheet = self._client.open_by_key(spreadsheet_id)
        if "!" in range_:
            sheet_name, bare_range = range_.split("!", 1)
            worksheet = spreadsheet.worksheet(sheet_name)
        else:
            worksheet = spreadsheet.sheet1
            bare_range = range_
        return worksheet, bare_range

    # ------------------------------------------------------------------
    # SheetsBackend interface
    # ------------------------------------------------------------------

    def read(self, spreadsheet_id: str, range_: str) -> SheetResult:
        """Read all values in *range_* and return them as a list-of-lists.

        Parameters
        ----------
        spreadsheet_id:
            The Google Sheets spreadsheet ID (the long hash in the URL).
        range_:
            A1 notation range, optionally prefixed with a sheet name
            (e.g. ``"Pipeline!A1:U"``).

        Returns
        -------
        SheetResult
            ``data`` is a ``list[list[str]]`` with the cell values.
        """
        try:
            worksheet, bare_range = self._open_sheet(spreadsheet_id, range_)
            values: list[list[str]] = worksheet.get(bare_range)
            return SheetResult(success=True, data=values)
        except SpreadsheetNotFound:
            return SheetResult(success=False, data=None, error=f"Spreadsheet not found: {spreadsheet_id}")
        except APIError as exc:
            return SheetResult(success=False, data=None, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return SheetResult(success=False, data=None, error=str(exc))

    def append(self, spreadsheet_id: str, range_: str, values: list[list[str]]) -> SheetResult:
        """Append *values* after the last row with data in *range_*.

        Parameters
        ----------
        spreadsheet_id:
            The Google Sheets spreadsheet ID.
        range_:
            A1 notation range used to determine which sheet and starting
            position for the append operation.
        values:
            Rows to append, each row being a list of cell values.

        Returns
        -------
        SheetResult
            ``data`` contains the gspread ``UpdatedProperties`` response on
            success.
        """
        try:
            worksheet, bare_range = self._open_sheet(spreadsheet_id, range_)
            result = worksheet.append_rows(
                values,
                value_input_option="USER_ENTERED",
                table_range=bare_range,
            )
            return SheetResult(success=True, data=result)
        except SpreadsheetNotFound:
            return SheetResult(success=False, data=None, error=f"Spreadsheet not found: {spreadsheet_id}")
        except APIError as exc:
            return SheetResult(success=False, data=None, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return SheetResult(success=False, data=None, error=str(exc))

    def update(self, spreadsheet_id: str, range_: str, values: list[list[str]]) -> SheetResult:
        """Overwrite *range_* with *values*.

        Parameters
        ----------
        spreadsheet_id:
            The Google Sheets spreadsheet ID.
        range_:
            A1 notation range to update (e.g. ``"Pipeline!A2:U2"``).
        values:
            New cell values; must match the shape of *range_*.

        Returns
        -------
        SheetResult
            ``data`` contains the gspread update response on success.
        """
        try:
            worksheet, bare_range = self._open_sheet(spreadsheet_id, range_)
            result = worksheet.update(bare_range, values, value_input_option="USER_ENTERED")
            return SheetResult(success=True, data=result)
        except SpreadsheetNotFound:
            return SheetResult(success=False, data=None, error=f"Spreadsheet not found: {spreadsheet_id}")
        except APIError as exc:
            return SheetResult(success=False, data=None, error=str(exc))
        except Exception as exc:  # noqa: BLE001
            return SheetResult(success=False, data=None, error=str(exc))
