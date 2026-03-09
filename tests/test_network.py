"""Unit tests for openclaw_crm.network module (spider network / signals)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openclaw_crm.network import (
    add_signal,
    check_competitor_guard,
    dismiss_signal,
    get_network_tree,
    get_network_value,
    get_pending_signals,
    promote_signal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SIGNAL_HEADERS = ["Timestamp", "Source Client", "Channel", "Signal Text", "Mentioned Company", "Status"]
PIPELINE_HEADERS = [
    "Client", "Contact", "Source", "Stage", "Budget", "Rate Type",
    "Service", "First Contact", "Last Contact", "Next Action",
    "Due Date", "Notes", "Slack Channel", "Proposal Link",
    "Owner", "Upwork URL", "Probability",
    "Referred By", "Network Parent", "Network Notes", "Signal Date",
]
CLIENT_HEADERS = ["Client", "Contact", "Status", "Since", "Budget", "Rate", "Service", "Notes", "Slack"]


def _make_sheet_result(values, success=True):
    r = MagicMock()
    r.success = success
    r.data = {"values": values}
    return r


def _empty():
    r = MagicMock()
    r.success = False
    r.data = None
    return r


def _signal_row(status="new", company="Acme", source="Alice"):
    return ["2026-01-01T00:00:00", source, "slack", "they need CRM", company, status]


def _pipeline_row(client="Acme", stage="lead", referred_by="", network_parent="", budget="5000"):
    row = [""] * len(PIPELINE_HEADERS)
    idx = {h: i for i, h in enumerate(PIPELINE_HEADERS)}
    row[idx["Client"]] = client
    row[idx["Stage"]] = stage
    row[idx["Budget"]] = budget
    row[idx["Referred By"]] = referred_by
    row[idx["Network Parent"]] = network_parent
    return row


# ---------------------------------------------------------------------------
# add_signal
# ---------------------------------------------------------------------------

class TestAddSignal:
    @patch("openclaw_crm.network.append_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_add_signal_returns_ok(self, _sid, mock_append):
        mock_append.return_value = MagicMock(success=True)
        result = add_signal({
            "source_client": "Alice",
            "channel": "slack",
            "signal_text": "They need help",
            "mentioned_company": "Globex",
        })
        assert result["ok"] is True
        assert result["status"] == "new"

    @patch("openclaw_crm.network.append_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_add_signal_failure(self, _sid, mock_append):
        mock_append.return_value = MagicMock(success=False)
        result = add_signal({"mentioned_company": "Fail"})
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# get_pending_signals
# ---------------------------------------------------------------------------

class TestGetPendingSignals:
    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_returns_only_new(self, _sid, mock_read):
        rows = [
            SIGNAL_HEADERS,
            _signal_row(status="new"),
            _signal_row(status="promoted"),
            _signal_row(status="dismissed"),
        ]
        mock_read.return_value = _make_sheet_result(rows)
        result = get_pending_signals()
        assert len(result) == 1
        assert result[0]["Status"] == "new"

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_empty_sheet(self, _sid, mock_read):
        mock_read.return_value = _make_sheet_result([SIGNAL_HEADERS])
        assert get_pending_signals() == []

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_case_insensitive_status(self, _sid, mock_read):
        row = _signal_row(status="NEW")
        rows = [SIGNAL_HEADERS, row]
        mock_read.return_value = _make_sheet_result(rows)
        # "NEW" != "new" after .lower() == "new" → should match
        result = get_pending_signals()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# promote_signal
# ---------------------------------------------------------------------------

class TestPromoteSignal:
    @patch("openclaw_crm.network.create_deal")
    @patch("openclaw_crm.network.update_sheet")
    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_promote_valid_signal(self, _sid, mock_read, mock_update, mock_deal):
        rows = [SIGNAL_HEADERS, _signal_row(status="new", company="Globex")]
        mock_read.return_value = _make_sheet_result(rows)
        mock_deal.return_value = {"ok": True, "row": 2}
        mock_update.return_value = MagicMock(success=True)
        result = promote_signal(2)
        assert result["ok"] is True

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_promote_out_of_range(self, _sid, mock_read):
        rows = [SIGNAL_HEADERS, _signal_row()]
        mock_read.return_value = _make_sheet_result(rows)
        result = promote_signal(99)
        assert result["ok"] is False

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_promote_already_promoted(self, _sid, mock_read):
        rows = [SIGNAL_HEADERS, _signal_row(status="promoted")]
        mock_read.return_value = _make_sheet_result(rows)
        result = promote_signal(2)
        assert result["ok"] is False

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_promote_empty_sheet(self, _sid, mock_read):
        mock_read.return_value = _empty()
        result = promote_signal(2)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# dismiss_signal
# ---------------------------------------------------------------------------

class TestDismissSignal:
    @patch("openclaw_crm.network.update_sheet")
    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_dismiss_valid(self, _sid, mock_read, mock_update):
        rows = [SIGNAL_HEADERS, _signal_row(status="new")]
        mock_read.return_value = _make_sheet_result(rows)
        mock_update.return_value = MagicMock(success=True)
        result = dismiss_signal(2)
        assert result["ok"] is True

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_dismiss_out_of_range(self, _sid, mock_read):
        rows = [SIGNAL_HEADERS, _signal_row()]
        mock_read.return_value = _make_sheet_result(rows)
        result = dismiss_signal(50)
        assert result["ok"] is False

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_dismiss_empty_sheet(self, _sid, mock_read):
        mock_read.return_value = _empty()
        result = dismiss_signal(2)
        assert result["ok"] is False


# ---------------------------------------------------------------------------
# get_network_tree
# ---------------------------------------------------------------------------

class TestGetNetworkTree:
    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_tree_groups_by_parent(self, _sid, mock_read):
        rows = [
            PIPELINE_HEADERS,
            _pipeline_row(client="Child1", referred_by="Parent"),
            _pipeline_row(client="Child2", network_parent="Parent"),
            _pipeline_row(client="Orphan"),
        ]
        mock_read.return_value = _make_sheet_result(rows)
        tree = get_network_tree()
        assert "Parent" in tree
        assert len(tree["Parent"]) == 2

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_tree_filtered_by_root(self, _sid, mock_read):
        rows = [
            PIPELINE_HEADERS,
            _pipeline_row(client="X", referred_by="Root"),
            _pipeline_row(client="Y", referred_by="Other"),
        ]
        mock_read.return_value = _make_sheet_result(rows)
        tree = get_network_tree(root="Root")
        assert "Root" in tree
        assert "Other" not in tree


# ---------------------------------------------------------------------------
# get_network_value
# ---------------------------------------------------------------------------

class TestGetNetworkValue:
    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_direct_and_network_value(self, _sid, mock_read):
        rows = [
            PIPELINE_HEADERS,
            _pipeline_row(client="Acme", budget="10000"),
            _pipeline_row(client="Referred", referred_by="Acme", budget="5000"),
        ]
        mock_read.return_value = _make_sheet_result(rows)
        result = get_network_value("Acme")
        assert result["direct_value"] == pytest.approx(10000)
        assert result["network_value"] == pytest.approx(5000)
        assert result["total"] == pytest.approx(15000)

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_unknown_client_returns_zeros(self, _sid, mock_read):
        rows = [PIPELINE_HEADERS, _pipeline_row(client="Other")]
        mock_read.return_value = _make_sheet_result(rows)
        result = get_network_value("Ghost")
        assert result["direct_value"] == 0
        assert result["network_value"] == 0


# ---------------------------------------------------------------------------
# check_competitor_guard
# ---------------------------------------------------------------------------

class TestCheckCompetitorGuard:
    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_competitor_already_active(self, _sid, mock_read):
        def side_effect(sid, range_):
            if "Pipeline" in range_:
                return _make_sheet_result([
                    PIPELINE_HEADERS,
                    _pipeline_row(client="CompetingCo", stage="won"),
                ])
            return _make_sheet_result([CLIENT_HEADERS])
        mock_read.side_effect = side_effect
        assert check_competitor_guard("CompetingCo", "Alice") is False

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_new_company_allowed(self, _sid, mock_read):
        def side_effect(sid, range_):
            if "Pipeline" in range_:
                return _make_sheet_result([PIPELINE_HEADERS])
            return _make_sheet_result([CLIENT_HEADERS])
        mock_read.side_effect = side_effect
        assert check_competitor_guard("BrandNew", "Alice") is True

    @patch("openclaw_crm.network.read_sheet")
    @patch("openclaw_crm.network.get_spreadsheet_id", return_value="sid")
    def test_case_insensitive_guard(self, _sid, mock_read):
        def side_effect(sid, range_):
            if "Pipeline" in range_:
                return _make_sheet_result([
                    PIPELINE_HEADERS,
                    _pipeline_row(client="competingco", stage="negotiation"),
                ])
            return _make_sheet_result([CLIENT_HEADERS])
        mock_read.side_effect = side_effect
        assert check_competitor_guard("COMPETINGCO", "Alice") is False
