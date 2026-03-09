"""Unit tests for GspreadBackend.

All gspread API calls are mocked; no network access is required.
"""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Stub the gspread package so tests run without the real library installed
# ---------------------------------------------------------------------------

def _make_gspread_stub():
    """Return a minimal gspread stub module hierarchy."""
    gspread = ModuleType("gspread")

    exceptions = ModuleType("gspread.exceptions")

    class APIError(Exception):
        pass

    class SpreadsheetNotFound(Exception):
        pass

    exceptions.APIError = APIError
    exceptions.SpreadsheetNotFound = SpreadsheetNotFound

    gspread.exceptions = exceptions
    gspread.APIError = APIError
    gspread.SpreadsheetNotFound = SpreadsheetNotFound

    sys.modules.setdefault("gspread", gspread)
    sys.modules.setdefault("gspread.exceptions", exceptions)
    return gspread


_gspread_stub = _make_gspread_stub()


# Now we can safely import the backend
from openclaw_crm.backends.gspread_backend import GspreadBackend  # noqa: E402
from openclaw_crm.sheets import SheetResult  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SPREADSHEET_ID = "fake_spreadsheet_id"
RANGE_SIMPLE = "A1:C3"
RANGE_WITH_SHEET = "Pipeline!A1:U"

SAMPLE_VALUES = [["Header1", "Header2"], ["val1", "val2"], ["val3", "val4"]]


def _make_backend() -> tuple[GspreadBackend, MagicMock, MagicMock]:
    """Return (backend, mock_client, mock_worksheet)."""
    mock_worksheet = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.sheet1 = mock_worksheet
    mock_spreadsheet.worksheet.return_value = mock_worksheet

    mock_client = MagicMock()
    mock_client.open_by_key.return_value = mock_spreadsheet

    backend = GspreadBackend(mock_client)
    return backend, mock_client, mock_worksheet


# ---------------------------------------------------------------------------
# __init__ / construction
# ---------------------------------------------------------------------------

class TestInit:
    def test_stores_client(self):
        mock_client = MagicMock()
        backend = GspreadBackend(mock_client)
        assert backend._client is mock_client


# ---------------------------------------------------------------------------
# read()
# ---------------------------------------------------------------------------

class TestRead:
    def test_read_simple_range(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.get.return_value = SAMPLE_VALUES

        result = backend.read(SPREADSHEET_ID, RANGE_SIMPLE)

        assert isinstance(result, SheetResult)
        assert result.success is True
        assert result.data == SAMPLE_VALUES
        mock_client.open_by_key.assert_called_once_with(SPREADSHEET_ID)
        mock_ws.get.assert_called_once_with(RANGE_SIMPLE)

    def test_read_range_with_sheet_name(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.get.return_value = SAMPLE_VALUES

        result = backend.read(SPREADSHEET_ID, RANGE_WITH_SHEET)

        assert result.success is True
        # Should call worksheet("Pipeline")
        mock_client.open_by_key.return_value.worksheet.assert_called_once_with("Pipeline")
        mock_ws.get.assert_called_once_with("A1:U")

    def test_read_uses_sheet1_when_no_bang(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.get.return_value = []

        backend.read(SPREADSHEET_ID, "A1:Z")
        # sheet1 should be used, not worksheet()
        mock_client.open_by_key.return_value.worksheet.assert_not_called()

    def test_read_spreadsheet_not_found(self):
        backend, mock_client, _ = _make_backend()
        mock_client.open_by_key.side_effect = _gspread_stub.SpreadsheetNotFound("not found")

        result = backend.read(SPREADSHEET_ID, RANGE_SIMPLE)

        assert result.success is False
        assert result.data is None
        assert SPREADSHEET_ID in result.error

    def test_read_api_error(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.get.side_effect = _gspread_stub.APIError("quota exceeded")

        result = backend.read(SPREADSHEET_ID, RANGE_SIMPLE)

        assert result.success is False
        assert "quota exceeded" in result.error

    def test_read_generic_exception(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.get.side_effect = RuntimeError("unexpected")

        result = backend.read(SPREADSHEET_ID, RANGE_SIMPLE)

        assert result.success is False
        assert "unexpected" in result.error

    def test_read_empty_sheet(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.get.return_value = []

        result = backend.read(SPREADSHEET_ID, RANGE_SIMPLE)

        assert result.success is True
        assert result.data == []


# ---------------------------------------------------------------------------
# append()
# ---------------------------------------------------------------------------

class TestAppend:
    def test_append_calls_append_rows(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.append_rows.return_value = {"updates": {"updatedRows": 2}}

        result = backend.append(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is True
        mock_ws.append_rows.assert_called_once_with(
            SAMPLE_VALUES,
            value_input_option="USER_ENTERED",
            table_range=RANGE_SIMPLE,
        )

    def test_append_with_sheet_name(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.append_rows.return_value = {}

        result = backend.append(SPREADSHEET_ID, RANGE_WITH_SHEET, SAMPLE_VALUES)

        assert result.success is True
        mock_ws.append_rows.assert_called_once_with(
            SAMPLE_VALUES,
            value_input_option="USER_ENTERED",
            table_range="A1:U",
        )

    def test_append_spreadsheet_not_found(self):
        backend, mock_client, _ = _make_backend()
        mock_client.open_by_key.side_effect = _gspread_stub.SpreadsheetNotFound("nope")

        result = backend.append(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is False
        assert result.data is None

    def test_append_api_error(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.append_rows.side_effect = _gspread_stub.APIError("rate limit")

        result = backend.append(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is False
        assert "rate limit" in result.error

    def test_append_generic_exception(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.append_rows.side_effect = ValueError("bad values")

        result = backend.append(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is False
        assert "bad values" in result.error


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_calls_worksheet_update(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.update.return_value = {"updatedCells": 6}

        result = backend.update(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is True
        mock_ws.update.assert_called_once_with(RANGE_SIMPLE, SAMPLE_VALUES, value_input_option="USER_ENTERED")

    def test_update_with_sheet_name(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.update.return_value = {}

        result = backend.update(SPREADSHEET_ID, RANGE_WITH_SHEET, SAMPLE_VALUES)

        assert result.success is True
        mock_ws.update.assert_called_once_with("A1:U", SAMPLE_VALUES, value_input_option="USER_ENTERED")

    def test_update_spreadsheet_not_found(self):
        backend, mock_client, _ = _make_backend()
        mock_client.open_by_key.side_effect = _gspread_stub.SpreadsheetNotFound("gone")

        result = backend.update(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is False
        assert result.data is None

    def test_update_api_error(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.update.side_effect = _gspread_stub.APIError("permission denied")

        result = backend.update(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is False
        assert "permission denied" in result.error

    def test_update_generic_exception(self):
        backend, mock_client, mock_ws = _make_backend()
        mock_ws.update.side_effect = TypeError("wrong type")

        result = backend.update(SPREADSHEET_ID, RANGE_SIMPLE, SAMPLE_VALUES)

        assert result.success is False
        assert "wrong type" in result.error
