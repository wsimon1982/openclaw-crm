"""Unit tests for openclaw_crm.pipeline module."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from openclaw_crm.pipeline import (
    STAGE_PROBABILITY,
    _days_since,
    _parse_rows,
    create_deal,
    get_overdue_invoices,
    get_pipeline,
    get_pipeline_summary,
    get_stale_deals,
    move_stage,
    update_deal,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_sheet_result(values: list[list[str]], success: bool = True):
    """Create a minimal mock that mimics a sheets result object."""
    result = MagicMock()
    result.success = success
    result.data = {"values": values}
    return result


def _empty_sheet_result():
    result = MagicMock()
    result.success = False
    result.data = None
    return result


PIPELINE_HEADERS = [
    "Client", "Contact", "Source", "Stage", "Budget", "Rate Type",
    "Service", "First Contact", "Last Contact", "Next Action",
    "Due Date", "Notes", "Slack Channel", "Proposal Link",
    "Owner", "Upwork URL", "Probability",
    "Referred By", "Network Parent", "Network Notes", "Signal Date",
]

REVENUE_HEADERS = ["Date", "Client", "Amount", "Status", "Invoice", "Notes"]


def _pipeline_row(**kwargs) -> list[str]:
    row = {
        "Client": "Acme", "Contact": "Alice", "Source": "upwork",
        "Stage": "lead", "Budget": "5000", "Rate Type": "fixed",
        "Service": "dev", "First Contact": "2026-01-01",
        "Last Contact": "2026-01-01", "Next Action": "call",
        "Due Date": "", "Notes": "", "Slack Channel": "",
        "Proposal Link": "", "Owner": "", "Upwork URL": "",
        "Probability": "0.1", "Referred By": "", "Network Parent": "",
        "Network Notes": "", "Signal Date": "",
    }
    row.update(kwargs)
    return [row[h] for h in PIPELINE_HEADERS]


# ---------------------------------------------------------------------------
# _parse_rows
# ---------------------------------------------------------------------------

class TestParseRows:
    def test_empty_result(self):
        assert _parse_rows(_empty_sheet_result()) == []

    def test_header_only(self):
        result = _make_sheet_result([PIPELINE_HEADERS])
        assert _parse_rows(result) == []

    def test_parses_single_row(self):
        row = _pipeline_row(Client="Globex")
        result = _make_sheet_result([PIPELINE_HEADERS, row])
        parsed = _parse_rows(result)
        assert len(parsed) == 1
        assert parsed[0]["Client"] == "Globex"

    def test_short_row_padded(self):
        """Rows shorter than headers should be zero-padded."""
        short = ["OnlyClient"]
        result = _make_sheet_result([PIPELINE_HEADERS, short])
        parsed = _parse_rows(result)
        assert parsed[0]["Stage"] == ""

    def test_multiple_rows(self):
        rows = [_pipeline_row(Client=f"Co{i}") for i in range(3)]
        result = _make_sheet_result([PIPELINE_HEADERS] + rows)
        assert [p["Client"] for p in _parse_rows(result)] == ["Co0", "Co1", "Co2"]


# ---------------------------------------------------------------------------
# _days_since
# ---------------------------------------------------------------------------

class TestDaysSince:
    def test_empty_string_returns_999(self):
        assert _days_since("") == 999

    def test_today_returns_zero(self):
        assert _days_since(date.today().isoformat()) == 0

    def test_invalid_format_returns_999(self):
        assert _days_since("not-a-date") == 999

    def test_past_date(self):
        # 2000-01-01 is always in the past
        assert _days_since("2000-01-01") > 0


# ---------------------------------------------------------------------------
# get_pipeline
# ---------------------------------------------------------------------------

class TestGetPipeline:
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_active_only_excludes_won_lost(self, _sid, mock_read):
        rows = [
            _pipeline_row(Client="A", Stage="lead"),
            _pipeline_row(Client="B", Stage="won"),
            _pipeline_row(Client="C", Stage="lost"),
            _pipeline_row(Client="D", Stage="proposal"),
        ]
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS] + rows)
        result = get_pipeline(active_only=True)
        clients = [d["Client"] for d in result]
        assert "A" in clients and "D" in clients
        assert "B" not in clients and "C" not in clients

    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_all_deals_when_not_active_only(self, _sid, mock_read):
        rows = [
            _pipeline_row(Client="A", Stage="won"),
            _pipeline_row(Client="B", Stage="lost"),
        ]
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS] + rows)
        result = get_pipeline(active_only=False)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# create_deal
# ---------------------------------------------------------------------------

class TestCreateDeal:
    @patch("openclaw_crm.pipeline.append_sheet")
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_create_deal_returns_ok(self, _sid, mock_read, mock_append):
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS])
        mock_append.return_value = MagicMock(success=True)
        result = create_deal({"client": "TestCo", "stage": "lead", "budget": "10000"})
        assert result["ok"] is True
        assert result["client"] == "TestCo"

    @patch("openclaw_crm.pipeline.append_sheet")
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_referred_by_sets_source_to_network(self, _sid, mock_read, mock_append):
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS])
        mock_append.return_value = MagicMock(success=True)
        result = create_deal({"client": "Netco", "referred_by": "Alice"})
        # row index 2 == "Source"
        assert result["row"] == 2

    @patch("openclaw_crm.pipeline.append_sheet")
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_row_number_increments(self, _sid, mock_read, mock_append):
        existing = [_pipeline_row() for _ in range(4)]
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS] + existing)
        mock_append.return_value = MagicMock(success=True)
        result = create_deal({"client": "NewCo"})
        assert result["row"] == 6  # 4 existing + header + 1


# ---------------------------------------------------------------------------
# update_deal
# ---------------------------------------------------------------------------

class TestUpdateDeal:
    @patch("openclaw_crm.pipeline.update_sheet")
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_update_stage(self, _sid, mock_read, mock_update):
        row = _pipeline_row(Client="Acme", Stage="lead")
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS, row])
        mock_update.return_value = MagicMock(success=True)
        result = update_deal(2, {"Stage": "proposal"})
        assert result["ok"] is True

    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_out_of_range_row(self, _sid, mock_read):
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS, _pipeline_row()])
        result = update_deal(99, {"Stage": "won"})
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# move_stage
# ---------------------------------------------------------------------------

class TestMoveStage:
    @patch("openclaw_crm.pipeline.update_sheet")
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_move_existing_client(self, _sid, mock_read, mock_update):
        row = _pipeline_row(Client="Acme", Stage="lead")
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS, row])
        mock_update.return_value = MagicMock(success=True)
        result = move_stage("Acme", "proposal")
        assert result["ok"] is True
        assert result["stage"] == "proposal"

    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_move_nonexistent_client(self, _sid, mock_read):
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS, _pipeline_row(Client="Other")])
        result = move_stage("Ghost", "won")
        assert result["ok"] is False

    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_move_stage_case_insensitive(self, _sid, mock_read):
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS])
        result = move_stage("Missing", "WON")
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# get_pipeline_summary
# ---------------------------------------------------------------------------

class TestGetPipelineSummary:
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_summary_counts(self, _sid, mock_read):
        rows = [
            _pipeline_row(Client="A", Stage="lead", Budget="1000"),
            _pipeline_row(Client="B", Stage="proposal", Budget="2000"),
            _pipeline_row(Client="C", Stage="won", Budget="5000"),
        ]
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS] + rows)
        summary = get_pipeline_summary()
        assert summary["total_deals"] == 2  # active only
        assert summary["won_deals"] == 1
        assert "lead" in summary["by_stage"]

    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_weighted_value_calculation(self, _sid, mock_read):
        rows = [_pipeline_row(Client="A", Stage="proposal", Budget="10000")]
        mock_read.return_value = _make_sheet_result([PIPELINE_HEADERS] + rows)
        summary = get_pipeline_summary()
        expected = 10000 * STAGE_PROBABILITY["proposal"]
        assert summary["total_weighted_value"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# get_stale_deals
# ---------------------------------------------------------------------------

class TestGetStaleDeals:
    @patch("openclaw_crm.pipeline.get_pipeline")
    def test_stale_deal_bucketed(self, mock_pipeline):
        mock_pipeline.return_value = [
            {**dict(zip(PIPELINE_HEADERS, _pipeline_row())), "Last Contact": "2020-01-01"},
        ]
        buckets = get_stale_deals([7, 14])
        assert len(buckets[14]) == 1

    @patch("openclaw_crm.pipeline.get_pipeline")
    def test_fresh_deal_not_in_buckets(self, mock_pipeline):
        mock_pipeline.return_value = [
            {**dict(zip(PIPELINE_HEADERS, _pipeline_row())), "Last Contact": date.today().isoformat()},
        ]
        buckets = get_stale_deals([7])
        assert len(buckets[7]) == 0


# ---------------------------------------------------------------------------
# get_overdue_invoices
# ---------------------------------------------------------------------------

class TestGetOverdueInvoices:
    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_overdue_invoice_detected(self, _sid, mock_read):
        rows = [
            REVENUE_HEADERS,
            ["2020-01-01", "Acme", "5000", "sent", "INV-001", ""],
        ]
        mock_read.return_value = _make_sheet_result(rows)
        result = get_overdue_invoices()
        assert len(result) == 1
        assert result[0]["_days_overdue"] > 30

    @patch("openclaw_crm.pipeline.read_sheet")
    @patch("openclaw_crm.pipeline.get_spreadsheet_id", return_value="sid")
    def test_paid_invoice_excluded(self, _sid, mock_read):
        rows = [
            REVENUE_HEADERS,
            ["2020-01-01", "Acme", "5000", "paid", "INV-001", ""],
        ]
        mock_read.return_value = _make_sheet_result(rows)
        result = get_overdue_invoices()
        assert result == []
