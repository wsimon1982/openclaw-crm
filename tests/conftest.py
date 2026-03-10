"""Pytest configuration and fixtures."""
import pytest
from openclaw_crm.backend import SheetsBackend


class MockBackend(SheetsBackend):
    """Mock backend for testing without real Google Sheets."""
    
    def __init__(self):
        self.data = {}
    
    def read_sheet(self, sheet_id, tab_name, range_name='A:Z'):
        """Return mock data."""
        return self.data.get(tab_name, [])
    
    def append_row(self, sheet_id, tab_name, values):
        """Append to mock data."""
        if tab_name not in self.data:
            self.data[tab_name] = []
        self.data[tab_name].append(values)
    
    def update_row(self, sheet_id, tab_name, row_index, values):
        """Update mock data."""
        if tab_name in self.data and 0 <= row_index < len(self.data[tab_name]):
            self.data[tab_name][row_index] = values


@pytest.fixture
def mock_backend():
    """Provide MockBackend instance for tests."""
    return MockBackend()
