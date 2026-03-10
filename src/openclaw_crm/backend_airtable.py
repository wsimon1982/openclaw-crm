"""Airtable backend for openclaw-crm."""
import os
from typing import Any
from pyairtable import Api, Table
from pyairtable.formulas import match


class AirtableBackend:
    """Airtable backend implementation."""
    
    def __init__(self, api_key: str = None, base_id: str = None):
        """Initialize Airtable backend.
        
        Args:
            api_key: Airtable API key (or from env AIRTABLE_API_KEY)
            base_id: Airtable base ID (or from env AIRTABLE_BASE_ID)
        """
        self.api_key = api_key or os.environ.get('AIRTABLE_API_KEY')
        self.base_id = base_id or os.environ.get('AIRTABLE_BASE_ID')
        
        if not self.api_key:
            raise ValueError("Airtable API key required (AIRTABLE_API_KEY)")
        if not self.base_id:
            raise ValueError("Airtable base ID required (AIRTABLE_BASE_ID)")
        
        self.api = Api(self.api_key)
        self.base = self.api.base(self.base_id)
    
    def get_table(self, table_name: str) -> Table:
        """Get Airtable table."""
        return self.base.table(table_name)
    
    def read_records(self, table_name: str, formula: str = None) -> list[dict]:
        """Read all records from table.
        
        Args:
            table_name: Name of the table (e.g., 'Pipeline', 'Network')
            formula: Optional Airtable formula filter
            
        Returns:
            List of records with 'id' and 'fields' keys
        """
        table = self.get_table(table_name)
        
        if formula:
            return table.all(formula=formula)
        return table.all()
    
    def create_record(self, table_name: str, fields: dict) -> dict:
        """Create a new record.
        
        Args:
            table_name: Name of the table
            fields: Dictionary of field values
            
        Returns:
            Created record with 'id' and 'fields'
        """
        table = self.get_table(table_name)
        return table.create(fields)
    
    def update_record(self, table_name: str, record_id: str, fields: dict) -> dict:
        """Update an existing record.
        
        Args:
            table_name: Name of the table
            record_id: Airtable record ID
            fields: Dictionary of fields to update
            
        Returns:
            Updated record
        """
        table = self.get_table(table_name)
        return table.update(record_id, fields)
    
    def delete_record(self, table_name: str, record_id: str) -> dict:
        """Delete a record.
        
        Args:
            table_name: Name of the table
            record_id: Airtable record ID
            
        Returns:
            Deleted record info
        """
        table = self.get_table(table_name)
        return table.delete(record_id)
    
    def find_record(self, table_name: str, field: str, value: Any) -> dict | None:
        """Find a record by field value.
        
        Args:
            table_name: Name of the table
            field: Field name to search
            value: Value to match
            
        Returns:
            First matching record or None
        """
        formula = match({field: value})
        records = self.read_records(table_name, formula=formula)
        return records[0] if records else None
    
    # Compatibility methods for sheets-like interface
    
    def read_sheet(self, base_id: str, table_name: str, range_name: str = None) -> list[list]:
        """Read records in sheets-like format (for compatibility).
        
        Returns:
            List of lists (rows), first row is headers
        """
        records = self.read_records(table_name)
        
        if not records:
            return []
        
        # Extract field names from first record
        headers = list(records[0]['fields'].keys())
        
        # Convert to rows
        rows = [headers]
        for record in records:
            row = [record['fields'].get(h, '') for h in headers]
            rows.append(row)
        
        return rows
    
    def append_row(self, base_id: str, table_name: str, values: list) -> dict:
        """Append a row (for sheets compatibility).
        
        Args:
            values: List of values (must match field order from read_sheet)
        """
        # Get headers to map values
        records = self.read_records(table_name)
        if records:
            headers = list(records[0]['fields'].keys())
        else:
            # Assume standard pipeline fields
            headers = ['Client', 'Contact', 'Source', 'Stage', 'Budget', 'Rate Type', 
                      'Service', 'Notes', 'Added', 'Updated']
        
        fields = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        return self.create_record(table_name, fields)
    
    def update_row(self, base_id: str, table_name: str, record_id: str, values: list) -> dict:
        """Update a row (for sheets compatibility)."""
        records = self.read_records(table_name)
        if records:
            headers = list(records[0]['fields'].keys())
            fields = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
            return self.update_record(table_name, record_id, fields)
        return {}
