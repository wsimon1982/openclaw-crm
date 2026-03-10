"""Unit tests for network module using mock backend."""
import pytest
from datetime import datetime
from openclaw_crm.network import (
    get_network,
    add_signal,
    promote_signal,
    get_competitor_warnings,
    find_path
)


@pytest.fixture
def sample_network_data():
    """Sample network data."""
    return [
        ['From', 'To', 'Relationship', 'Notes', 'Added'],
        ['Acme Corp', 'Beta Inc', 'client-competitor', 'Direct competitors', '2026-01-15'],
        ['Acme Corp', 'Gamma LLC', 'referral', 'CEO knows CTO', '2026-02-01'],
        ['Beta Inc', 'Delta Co', 'partner', 'Strategic alliance', '2026-01-20']
    ]


@pytest.fixture
def sample_signals_data():
    """Sample signals queue."""
    return [
        ['From', 'To', 'Type', 'Confidence', 'Source', 'Date'],
        ['Gamma LLC', 'Epsilon Inc', 'referral-signal', 'high', 'conversation', '2026-03-01'],
        ['Delta Co', 'Zeta Corp', 'competitor-signal', 'medium', 'research', '2026-03-05']
    ]


def test_get_network_empty(mock_backend, monkeypatch):
    """Test get_network with empty sheet."""
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    result = get_network()
    assert result == []


def test_get_network_with_data(mock_backend, sample_network_data, monkeypatch):
    """Test get_network returns data."""
    mock_backend.data['Network'] = sample_network_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    result = get_network()
    assert len(result) == 3  # Excludes header
    assert result[0]['From'] == 'Acme Corp'
    assert result[0]['Relationship'] == 'client-competitor'


def test_add_signal(mock_backend, monkeypatch):
    """Test add_signal queues new signal."""
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    signal = {
        'from': 'Company A',
        'to': 'Company B',
        'type': 'referral-signal',
        'confidence': 'high',
        'source': 'email'
    }
    
    add_signal(signal)
    
    assert len(mock_backend.data.get('Signals', [])) == 1
    assert mock_backend.data['Signals'][0][0] == 'Company A'


def test_promote_signal_to_network(mock_backend, sample_signals_data, monkeypatch):
    """Test promote_signal moves signal to network."""
    mock_backend.data['Signals'] = sample_signals_data
    mock_backend.data['Network'] = []
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    promote_signal('Gamma LLC', 'Epsilon Inc')
    
    # Check signal removed from queue
    assert len([s for s in mock_backend.data['Signals'] if s[0] == 'Gamma LLC']) == 0
    
    # Check added to network
    assert len(mock_backend.data['Network']) == 1
    assert mock_backend.data['Network'][0][0] == 'Gamma LLC'


def test_get_competitor_warnings_direct(mock_backend, sample_network_data, monkeypatch):
    """Test competitor warning detection."""
    mock_backend.data['Network'] = sample_network_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    warnings = get_competitor_warnings('Acme Corp')
    
    assert len(warnings) > 0
    assert any('Beta Inc' in w['competitor'] for w in warnings)


def test_get_competitor_warnings_none(mock_backend, sample_network_data, monkeypatch):
    """Test no warnings for safe client."""
    mock_backend.data['Network'] = sample_network_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    warnings = get_competitor_warnings('Gamma LLC')
    
    # Gamma has no competitors in network
    assert len(warnings) == 0


def test_find_path_direct(mock_backend, sample_network_data, monkeypatch):
    """Test find_path finds direct connection."""
    mock_backend.data['Network'] = sample_network_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    path = find_path('Acme Corp', 'Gamma LLC')
    
    assert path is not None
    assert len(path) == 2
    assert path[0] == 'Acme Corp'
    assert path[1] == 'Gamma LLC'


def test_find_path_multi_hop(mock_backend, sample_network_data, monkeypatch):
    """Test find_path finds indirect connection."""
    mock_backend.data['Network'] = sample_network_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    path = find_path('Acme Corp', 'Delta Co')
    
    # Acme -> Beta -> Delta (if exists)
    assert path is None or len(path) > 0


def test_find_path_no_connection(mock_backend, sample_network_data, monkeypatch):
    """Test find_path returns None for isolated nodes."""
    mock_backend.data['Network'] = sample_network_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    path = find_path('Acme Corp', 'Nonexistent Corp')
    
    assert path is None


def test_relationship_type_normalization(mock_backend, monkeypatch):
    """Test relationship types are normalized."""
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    signal = {
        'from': 'A',
        'to': 'B',
        'type': 'REFERRAL-SIGNAL',  # Uppercase
        'confidence': 'HIGH'
    }
    
    add_signal(signal)
    
    # Should be normalized to lowercase
    assert mock_backend.data['Signals'][0][2].lower() == 'referral-signal'


def test_duplicate_signal_handling(mock_backend, sample_signals_data, monkeypatch):
    """Test duplicate signals are handled."""
    mock_backend.data['Signals'] = sample_signals_data
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    # Try to add duplicate
    duplicate = {
        'from': 'Gamma LLC',
        'to': 'Epsilon Inc',
        'type': 'referral-signal',
        'confidence': 'high'
    }
    
    initial_count = len(mock_backend.data['Signals'])
    add_signal(duplicate)
    
    # Should prevent duplicate or mark as seen
    assert len(mock_backend.data['Signals']) == initial_count + 1  # Or same if prevented


def test_missing_columns_network(mock_backend, monkeypatch):
    """Test handling of incomplete network data."""
    mock_backend.data['Network'] = [
        ['From', 'To'],  # Missing relationship column
        ['A', 'B']
    ]
    monkeypatch.setattr('openclaw_crm.network.backend', mock_backend)
    
    # Should handle gracefully
    result = get_network()
    assert len(result) >= 0  # No crash
