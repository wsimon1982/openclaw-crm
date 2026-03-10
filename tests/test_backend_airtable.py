"""Unit tests for Airtable backend."""
import pytest
from unittest.mock import Mock, patch
from openclaw_crm.backend_airtable import AirtableBackend


@pytest.fixture
def mock_airtable_api():
    """Mock Airtable API."""
    with patch('openclaw_crm.backend_airtable.Api') as mock_api:
        mock_base = Mock()
        mock_table = Mock()
        
        mock_api.return_value.base.return_value = mock_base
        mock_base.table.return_value = mock_table
        
        yield mock_api, mock_base, mock_table


def test_backend_init_with_keys():
    """Test backend initialization with explicit keys."""
    backend = AirtableBackend(api_key='test_key', base_id='test_base')
    assert backend.api_key == 'test_key'
    assert backend.base_id == 'test_base'


def test_backend_init_from_env(monkeypatch):
    """Test backend initialization from environment."""
    monkeypatch.setenv('AIRTABLE_API_KEY', 'env_key')
    monkeypatch.setenv('AIRTABLE_BASE_ID', 'env_base')
    
    backend = AirtableBackend()
    assert backend.api_key == 'env_key'
    assert backend.base_id == 'env_base'


def test_backend_init_missing_key():
    """Test backend raises error without API key."""
    with pytest.raises(ValueError, match="API key required"):
        AirtableBackend(base_id='test')


def test_read_records(mock_airtable_api):
    """Test read_records returns data."""
    mock_api, mock_base, mock_table = mock_airtable_api
    
    mock_table.all.return_value = [
        {'id': 'rec1', 'fields': {'Client': 'Acme', 'Stage': 'lead'}},
        {'id': 'rec2', 'fields': {'Client': 'Beta', 'Stage': 'won'}}
    ]
    
    backend = AirtableBackend(api_key='key', base_id='base')
    records = backend.read_records('Pipeline')
    
    assert len(records) == 2
    assert records[0]['fields']['Client'] == 'Acme'
    mock_table.all.assert_called_once()


def test_create_record(mock_airtable_api):
    """Test create_record adds new record."""
    mock_api, mock_base, mock_table = mock_airtable_api
    
    mock_table.create.return_value = {'id': 'rec3', 'fields': {'Client': 'Gamma'}}
    
    backend = AirtableBackend(api_key='key', base_id='base')
    result = backend.create_record('Pipeline', {'Client': 'Gamma', 'Stage': 'lead'})
    
    assert result['id'] == 'rec3'
    mock_table.create.assert_called_once_with({'Client': 'Gamma', 'Stage': 'lead'})


def test_update_record(mock_airtable_api):
    """Test update_record modifies existing."""
    mock_api, mock_base, mock_table = mock_airtable_api
    
    mock_table.update.return_value = {'id': 'rec1', 'fields': {'Stage': 'won'}}
    
    backend = AirtableBackend(api_key='key', base_id='base')
    result = backend.update_record('Pipeline', 'rec1', {'Stage': 'won'})
    
    assert result['fields']['Stage'] == 'won'
    mock_table.update.assert_called_once()


def test_delete_record(mock_airtable_api):
    """Test delete_record removes record."""
    mock_api, mock_base, mock_table = mock_airtable_api
    
    mock_table.delete.return_value = {'deleted': True, 'id': 'rec1'}
    
    backend = AirtableBackend(api_key='key', base_id='base')
    result = backend.delete_record('Pipeline', 'rec1')
    
    assert result['deleted']
    mock_table.delete.assert_called_once_with('rec1')


def test_find_record(mock_airtable_api):
    """Test find_record by field value."""
    mock_api, mock_base, mock_table = mock_airtable_api
    
    mock_table.all.return_value = [
        {'id': 'rec1', 'fields': {'Client': 'Acme'}}
    ]
    
    backend = AirtableBackend(api_key='key', base_id='base')
    result = backend.find_record('Pipeline', 'Client', 'Acme')
    
    assert result is not None
    assert result['fields']['Client'] == 'Acme'


def test_read_sheet_compatibility(mock_airtable_api):
    """Test sheets-like read interface."""
    mock_api, mock_base, mock_table = mock_airtable_api
    
    mock_table.all.return_value = [
        {'id': 'rec1', 'fields': {'Client': 'Acme', 'Stage': 'lead'}},
        {'id': 'rec2', 'fields': {'Client': 'Beta', 'Stage': 'won'}}
    ]
    
    backend = AirtableBackend(api_key='key', base_id='base')
    rows = backend.read_sheet('base', 'Pipeline')
    
    assert len(rows) == 3  # Header + 2 data rows
    assert rows[0] == ['Client', 'Stage']  # Headers
    assert rows[1] == ['Acme', 'lead']
