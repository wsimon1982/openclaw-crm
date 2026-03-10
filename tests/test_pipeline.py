"""Unit tests for pipeline module using mock backend."""
import pytest
from datetime import datetime, timedelta
from openclaw_crm.pipeline import (
    get_pipeline,
    create_deal,
    move_stage,
    get_pipeline_summary,
    get_stale_deals
)


class MockBackend:
    """Mock SheetsBackend for testing."""
    
    def __init__(self):
        self.data = {
            'Pipeline': [],
            'Network': []
        }
    
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
        if tab_name in self.data and row_index < len(self.data[tab_name]):
            self.data[tab_name][row_index] = values


@pytest.fixture
def mock_backend():
    """Fixture providing MockBackend instance."""
    return MockBackend()


@pytest.fixture
def sample_pipeline_data():
    """Sample pipeline data."""
    return [
        ['Client', 'Contact', 'Source', 'Stage', 'Budget', 'Rate Type', 'Service'],
        ['Acme Corp', 'John Doe', 'upwork', 'lead', '15000', 'fixed', 'Development'],
        ['Beta Inc', 'Jane Smith', 'network', 'proposal', '25000', 'hourly', 'Consulting'],
        ['Gamma LLC', 'Bob Johnson', 'inbound', 'won', '10000', 'retainer', 'Support']
    ]


def test_get_pipeline_empty_sheet(mock_backend, monkeypatch):
    """Test get_pipeline with empty sheet."""
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    result = get_pipeline()
    assert result == []


def test_get_pipeline_with_data(mock_backend, sample_pipeline_data, monkeypatch):
    """Test get_pipeline returns data."""
    mock_backend.data['Pipeline'] = sample_pipeline_data
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    result = get_pipeline()
    assert len(result) == 3  # Excludes header
    assert result[0]['Client'] == 'Acme Corp'
    assert result[1]['Stage'] == 'proposal'


def test_create_deal(mock_backend, monkeypatch):
    """Test create_deal adds new deal."""
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    deal_data = {
        'client': 'New Client',
        'contact': 'Test Contact',
        'source': 'referral',
        'stage': 'lead',
        'budget': '5000'
    }
    
    create_deal(deal_data)
    
    assert len(mock_backend.data['Pipeline']) == 1
    assert mock_backend.data['Pipeline'][0][0] == 'New Client'


def test_move_stage(mock_backend, sample_pipeline_data, monkeypatch):
    """Test move_stage updates deal stage."""
    mock_backend.data['Pipeline'] = sample_pipeline_data
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    move_stage('Acme Corp', 'qualifying')
    
    updated_row = mock_backend.data['Pipeline'][1]
    assert updated_row[3] == 'qualifying'


def test_move_stage_normalization(mock_backend, sample_pipeline_data, monkeypatch):
    """Test stage name normalization."""
    mock_backend.data['Pipeline'] = sample_pipeline_data
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    # Test various formats
    move_stage('Acme Corp', 'QUALIFYING')
    assert mock_backend.data['Pipeline'][1][3].lower() == 'qualifying'


def test_get_pipeline_summary_empty(mock_backend, monkeypatch):
    """Test summary with empty pipeline."""
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    summary = get_pipeline_summary()
    assert summary['total_deals'] == 0
    assert summary['total_value'] == 0


def test_get_pipeline_summary_with_data(mock_backend, sample_pipeline_data, monkeypatch):
    """Test summary calculates correctly."""
    mock_backend.data['Pipeline'] = sample_pipeline_data
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    summary = get_pipeline_summary()
    assert summary['total_deals'] == 3
    assert summary['total_value'] == 50000  # 15k + 25k + 10k


def test_get_stale_deals_empty(mock_backend, monkeypatch):
    """Test stale deals with empty pipeline."""
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    stale = get_stale_deals(days=7)
    assert stale == []


def test_get_stale_deals_threshold(mock_backend, monkeypatch):
    """Test stale deals detection."""
    old_date = (datetime.now() - timedelta(days=10)).isoformat()
    recent_date = datetime.now().isoformat()
    
    mock_backend.data['Pipeline'] = [
        ['Client', 'Contact', 'Source', 'Stage', 'Budget', 'Updated'],
        ['Old Deal', 'Contact1', 'upwork', 'lead', '5000', old_date],
        ['Recent Deal', 'Contact2', 'network', 'proposal', '3000', recent_date]
    ]
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    stale = get_stale_deals(days=7)
    assert len(stale) == 1
    assert stale[0]['Client'] == 'Old Deal'


def test_missing_columns_handling(mock_backend, monkeypatch):
    """Test handling of incomplete data."""
    mock_backend.data['Pipeline'] = [
        ['Client', 'Stage'],  # Missing columns
        ['Incomplete Corp', 'lead']
    ]
    monkeypatch.setattr('openclaw_crm.pipeline.backend', mock_backend)
    
    # Should handle gracefully
    result = get_pipeline()
    assert len(result) >= 0  # No crash
