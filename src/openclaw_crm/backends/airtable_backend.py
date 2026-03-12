"""Airtable storage backend for openclaw-crm.

Usage:
    export AIRTABLE_API_TOKEN=pat_xxxxxxxxxxxxxxxx
    export AIRTABLE_BASE_ID=appXXXXXXXXXXXXXX

Or via config:
    from openclaw_crm.backends.airtable_backend import AirtableBackend
    backend = AirtableBackend(base_id="appXXX", api_token="patXXX")
"""

from __future__ import annotations

import os
from typing import Any

from openclaw_crm.sheets import SheetResult, SheetsBackend

try:
    from pyairtable import Api
    from pyairtable.models.schema import TableSchema

    PYAIRTABLE_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYAIRTABLE_AVAILABLE = False


# Maps pipeline column names → Airtable field names (override via subclass or config)
DEFAULT_FIELD_MAP: dict[str, str] = {
    "Name": "Name",
    "Status": "Status",
    "Email": "Email",
    "Phone": "Phone",
    "Company": "Company",
    "Notes": "Notes",
    "CreatedAt": "Created At",
}


class AirtableBackend(SheetsBackend):
    """Airtable-backed storage that satisfies the SheetsBackend interface.

    Args:
        base_id: Airtable Base ID (e.g. ``appXXXXXXXXXXXXXX``).
            Falls back to env var ``AIRTABLE_BASE_ID``.
        api_token: Airtable personal access token.
            Falls back to env var ``AIRTABLE_API_TOKEN``.
        field_map: Optional mapping from generic column names to Airtable field
            names. Defaults to :data:`DEFAULT_FIELD_MAP`.
    """

    def __init__(
        self,
        base_id: str | None = None,
        api_token: str | None = None,
        field_map: dict[str, str] | None = None,
    ) -> None:
        if not PYAIRTABLE_AVAILABLE:
            raise ImportError(
                "pyairtable is required for AirtableBackend. "
                "Install it with: pip install 'openclaw-crm[airtable]'"
            )

        self.base_id = base_id or os.environ.get("AIRTABLE_BASE_ID", "")
        self.api_token = api_token or os.environ.get("AIRTABLE_API_TOKEN", "")
        self.field_map = field_map or DEFAULT_FIELD_MAP

        if not self.base_id:
            raise ValueError(
                "Airtable base_id is required. "
                "Pass it directly or set AIRTABLE_BASE_ID env var."
            )
        if not self.api_token:
            raise ValueError(
                "Airtable api_token is required. "
                "Pass it directly or set AIRTABLE_API_TOKEN env var."
            )

        self._api = Api(self.api_token)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_table(self, table_name: str):
        """Return a pyairtable Table object for *table_name*."""
        return self._api.table(self.base_id, table_name)

    def _parse_table_ref(self, spreadsheet_id: str, range_: str) -> tuple[str, str | None]:
        """Parse (table_name, view_or_field) from the generic range_ string.

        The ``spreadsheet_id`` is treated as the Airtable table name.
        ``range_`` can optionally specify a view name like ``"viw_xxxx"``
        or a field filter expression like ``"Status=Active"``.
        """
        return spreadsheet_id, range_ or None

    def _rows_to_values(self, records: list[dict[str, Any]]) -> list[list[str]]:
        """Convert Airtable records to a list-of-lists (SheetsBackend format)."""
        if not records:
            return []
        # Collect all field keys in order
        all_keys: list[str] = []
        seen: set[str] = set()
        for rec in records:
            for k in rec.get("fields", {}).keys():
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        # Header row + data rows
        header = [self.field_map.get(k, k) for k in all_keys]
        rows = [
            [str(rec.get("fields", {}).get(k, "")) for k in all_keys]
            for rec in records
        ]
        return [header, *rows]

    def _values_to_fields(self, values: list[list[str]]) -> list[dict[str, str]]:
        """Convert list-of-lists to Airtable field dicts.

        First row is treated as the header.
        """
        if len(values) < 2:
            return []
        header = values[0]
        reverse_map = {v: k for k, v in self.field_map.items()}
        result = []
        for row in values[1:]:
            fields: dict[str, str] = {}
            for col, val in zip(header, row):
                field_name = reverse_map.get(col, col)
                fields[field_name] = val
            result.append(fields)
        return result

    # ------------------------------------------------------------------
    # SheetsBackend interface
    # ------------------------------------------------------------------

    def read(self, spreadsheet_id: str, range_: str) -> SheetResult:
        """Read all records from an Airtable table.

        Args:
            spreadsheet_id: Airtable table name (e.g. ``"Pipeline"``).
            range_: Optional view name or ignored for full-table reads.

        Returns:
            :class:`~openclaw_crm.sheets.SheetResult` with ``data`` as
            list-of-lists (header + rows).
        """
        try:
            table_name, _ = self._parse_table_ref(spreadsheet_id, range_)
            table = self._get_table(table_name)
            records = table.all()
            return SheetResult(success=True, data=self._rows_to_values(records))
        except Exception as exc:  # noqa: BLE001
            return SheetResult(success=False, data=None, error=str(exc))

    def append(self, spreadsheet_id: str, range_: str, values: list[list[str]]) -> SheetResult:
        """Append rows to an Airtable table.

        Args:
            spreadsheet_id: Airtable table name.
            range_: Ignored (Airtable always appends to the table).
            values: List-of-lists where the first row is the header.

        Returns:
            :class:`~openclaw_crm.sheets.SheetResult` with ``data`` as
            the list of created record IDs.
        """
        try:
            table_name, _ = self._parse_table_ref(spreadsheet_id, range_)
            table = self._get_table(table_name)
            records_to_create = self._values_to_fields(values)
            if not records_to_create:
                return SheetResult(success=True, data=[])
            created = table.batch_create(records_to_create)
            ids = [r["id"] for r in created]
            return SheetResult(success=True, data=ids)
        except Exception as exc:  # noqa: BLE001
            return SheetResult(success=False, data=None, error=str(exc))

    def update(self, spreadsheet_id: str, range_: str, values: list[list[str]]) -> SheetResult:
        """Update existing records in an Airtable table.

        ``range_`` is expected to contain a record ID (``recXXXXXXXXXXXXXX``)
        when updating a single record, or is ignored for batch updates where
        the first column of each row must be the record ID.

        Args:
            spreadsheet_id: Airtable table name.
            range_: Record ID for single-record updates, or ``"batch"``
                for multi-record updates (first column = record ID).
            values: List-of-lists (header + rows).

        Returns:
            :class:`~openclaw_crm.sheets.SheetResult` with updated record IDs.
        """
        try:
            table_name, record_id = self._parse_table_ref(spreadsheet_id, range_)
            table = self._get_table(table_name)
            fields_list = self._values_to_fields(values)

            if record_id and record_id.startswith("rec") and len(fields_list) == 1:
                # Single-record update
                updated = table.update(record_id, fields_list[0])
                return SheetResult(success=True, data=[updated["id"]])

            # Batch update: first field in each dict should map to a record ID column
            # We look for an "id" or "record_id" key and use it as the Airtable ID.
            updates = []
            for fields in fields_list:
                rid = fields.pop("id", None) or fields.pop("record_id", None)
                if rid:
                    updates.append({"id": rid, "fields": fields})

            if not updates:
                return SheetResult(
                    success=False,
                    data=None,
                    error="No record IDs found for batch update. "
                    "Include an 'id' column with Airtable record IDs.",
                )

            updated_records = table.batch_update(updates)
            return SheetResult(success=True, data=[r["id"] for r in updated_records])
        except Exception as exc:  # noqa: BLE001
            return SheetResult(success=False, data=None, error=str(exc))
