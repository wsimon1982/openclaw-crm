"""Tests for AirtableBackend using mocked pyairtable responses."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RECORDS = [
    {
        "id": "recABC123",
        "fields": {"Name": "Alice", "Status": "Active", "Email": "alice@example.com"},
        "createdTime": "2024-01-01T00:00:00.000Z",
    },
    {
        "id": "recDEF456",
        "fields": {"Name": "Bob", "Status": "Lead", "Email": "bob@example.com"},
        "createdTime": "2024-01-02T00:00:00.000Z",
    },
]


def _make_backend(mock_api_cls):
    """Instantiate AirtableBackend with mocked pyairtable.Api."""
    mock_api_cls.return_value = MagicMock()
    from openclaw_crm.backends.airtable_backend import AirtableBackend

    return AirtableBackend(base_id="appTEST", api_token="patTEST")


# ---------------------------------------------------------------------------
# Import / init tests
# ---------------------------------------------------------------------------


def test_import_error_without_pyairtable():
    """AirtableBackend raises ImportError when pyairtable is unavailable."""
    import sys
    import importlib

    with patch.dict(sys.modules, {"pyairtable": None}):
        # Force reload so the try/except runs with pyairtable missing
        import openclaw_crm.backends.airtable_backend as mod
        importlib.reload(mod)
        with pytest.raises(ImportError, match="pyairtable"):
            mod.AirtableBackend(base_id="app", api_token="tok")

    # Restore normal module state
    importlib.reload(mod)


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_missing_base_id_raises(mock_api_cls):
    from openclaw_crm.backends.airtable_backend import AirtableBackend

    with pytest.raises(ValueError, match="base_id"):
        AirtableBackend(base_id="", api_token="patTEST")


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_missing_api_token_raises(mock_api_cls):
    from openclaw_crm.backends.airtable_backend import AirtableBackend

    with pytest.raises(ValueError, match="api_token"):
        AirtableBackend(base_id="appTEST", api_token="")


# ---------------------------------------------------------------------------
# read()
# ---------------------------------------------------------------------------


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_read_returns_header_and_rows(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.all.return_value = SAMPLE_RECORDS
    backend._api.table.return_value = mock_table

    result = backend.read("Pipeline", "Grid view")

    assert result.success is True
    assert result.data[0] == ["Name", "Status", "Email"]  # header
    assert result.data[1] == ["Alice", "Active", "alice@example.com"]
    assert result.data[2] == ["Bob", "Lead", "bob@example.com"]


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_read_empty_table(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.all.return_value = []
    backend._api.table.return_value = mock_table

    result = backend.read("Pipeline", "")

    assert result.success is True
    assert result.data == []


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_read_api_error(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.all.side_effect = Exception("API error")
    backend._api.table.return_value = mock_table

    result = backend.read("Pipeline", "")

    assert result.success is False
    assert "API error" in result.error


# ---------------------------------------------------------------------------
# append()
# ---------------------------------------------------------------------------


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_append_creates_records(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.batch_create.return_value = [{"id": "recNEW001"}, {"id": "recNEW002"}]
    backend._api.table.return_value = mock_table

    values = [
        ["Name", "Status"],
        ["Charlie", "Active"],
        ["Dana", "Lead"],
    ]
    result = backend.append("Pipeline", "", values)

    assert result.success is True
    assert result.data == ["recNEW001", "recNEW002"]
    mock_table.batch_create.assert_called_once_with(
        [{"Name": "Charlie", "Status": "Active"}, {"Name": "Dana", "Status": "Lead"}]
    )


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_append_empty_values(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    backend._api.table.return_value = mock_table

    result = backend.append("Pipeline", "", [["Name"]])  # header only, no rows

    assert result.success is True
    assert result.data == []
    mock_table.batch_create.assert_not_called()


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_append_api_error(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.batch_create.side_effect = Exception("rate limit")
    backend._api.table.return_value = mock_table

    result = backend.append("Pipeline", "", [["Name"], ["Eve"]])

    assert result.success is False
    assert "rate limit" in result.error


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_update_single_record(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.update.return_value = {"id": "recABC123", "fields": {"Status": "Closed"}}
    backend._api.table.return_value = mock_table

    values = [["Status"], ["Closed"]]
    result = backend.update("Pipeline", "recABC123", values)

    assert result.success is True
    assert result.data == ["recABC123"]
    mock_table.update.assert_called_once_with("recABC123", {"Status": "Closed"})


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_update_batch_records(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.batch_update.return_value = [
        {"id": "recABC123"},
        {"id": "recDEF456"},
    ]
    backend._api.table.return_value = mock_table

    values = [
        ["id", "Status"],
        ["recABC123", "Closed"],
        ["recDEF456", "Won"],
    ]
    result = backend.update("Pipeline", "batch", values)

    assert result.success is True
    assert result.data == ["recABC123", "recDEF456"]


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_update_no_record_ids_returns_error(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    backend._api.table.return_value = mock_table

    values = [["Name", "Status"], ["Alice", "Active"]]
    result = backend.update("Pipeline", "batch", values)

    assert result.success is False
    assert "record IDs" in result.error


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_update_api_error(mock_api_cls):
    backend = _make_backend(mock_api_cls)
    mock_table = MagicMock()
    mock_table.update.side_effect = Exception("not found")
    backend._api.table.return_value = mock_table

    result = backend.update("Pipeline", "recABC123", [["Status"], ["Closed"]])

    assert result.success is False
    assert "not found" in result.error


# ---------------------------------------------------------------------------
# field_map
# ---------------------------------------------------------------------------


@patch("openclaw_crm.backends.airtable_backend.Api")
def test_custom_field_map(mock_api_cls):
    """Custom field_map is applied when reading records."""
    mock_api_cls.return_value = MagicMock()
    from openclaw_crm.backends.airtable_backend import AirtableBackend

    backend = AirtableBackend(
        base_id="appTEST",
        api_token="patTEST",
        field_map={"Name": "Contact Name"},
    )
    mock_table = MagicMock()
    mock_table.all.return_value = [{"id": "rec1", "fields": {"Name": "Alice"}}]
    backend._api.table.return_value = mock_table

    result = backend.read("Pipeline", "")

    assert result.success is True
    assert result.data[0] == ["Contact Name"]  # mapped header
