"""
Tests for the transactions visualization module.
"""

import pytest
import pandas as pd
import tempfile
import os
from datetime import datetime
from src.transactions_visualize import PortfolioFlowTracker, Position, FundSource


class TestPortfolioFlowTracker:
    """Test cases for PortfolioFlowTracker class."""
    
    def test_initialization(self):
        """Test that the tracker initializes correctly."""
        tracker = PortfolioFlowTracker()
        assert tracker.node_labels == ["Initial Cash"]
        assert len(tracker.node_colors) == 1
        assert len(tracker.positions) == 0
        assert len(tracker.available_funds) == 0
    
    def test_get_stock_currency(self):
        """Test currency detection for stocks."""
        tracker = PortfolioFlowTracker()
        # Test with a known stock
        currency = tracker._get_stock_currency("MSFT")
        assert currency == "USD"
    
    def test_convert_to_usd(self):
        """Test currency conversion to USD."""
        tracker = PortfolioFlowTracker()
        date = datetime(2020, 1, 1)
        
        # Test USD to USD (no conversion)
        result = tracker._to_usd(100.0, "USD", date)
        assert result == 100.0
        
        # Test EUR to USD (with actual rate from data or default)
        result = tracker._to_usd(100.0, "EUR", date)
        assert result > 0  # Should be positive
        assert isinstance(result, float)
    
    def test_add_node(self):
        """Test node addition."""
        tracker = PortfolioFlowTracker()
        node_idx = tracker._add_node("AAPL")
        assert node_idx == 1  # After Initial Cash
        assert "AAPL" in tracker.node_labels
        assert len(tracker.node_colors) == 2
    
    def test_process_sell_transaction(self):
        """Test sell transaction processing."""
        tracker = PortfolioFlowTracker()
        transaction = pd.Series({
            'symbol': 'AAPL',
            'quantity': 10.0,
            'price': 150.0,
            'date': '2020-01-01',
            'source': 'Funds'
        })
        usd_value = tracker._process_sell_transaction(transaction)
        assert usd_value == 1500.0
        assert len(tracker.available_funds) == 1
        assert tracker.available_funds[0].source_type == 'sell'
    
    def test_process_buy_transaction(self):
        """Test buy transaction processing."""
        tracker = PortfolioFlowTracker()
        transaction = pd.Series({
            'symbol': 'AAPL',
            'quantity': 10.0,
            'price': 150.0,
            'date': '2020-01-01',
            'source': 'Funds'
        })
        usd_value = tracker._process_buy_transaction(transaction)
        assert usd_value == 1500.0
        assert 'AAPL' in tracker.positions
        assert tracker.positions['AAPL'].quantity == 10.0
    
    def test_process_employment_transaction(self):
        """Test employment transaction processing."""
        tracker = PortfolioFlowTracker()
        transaction = pd.Series({
            'symbol': 'WDAY',
            'quantity': 100.0,
            'price': 200.0,
            'date': '2020-01-01',
            'source': 'RSU'
        })
        usd_value = tracker._process_employment_transaction(transaction)
        assert usd_value == 20000.0
        assert len(tracker.available_funds) == 1
        assert tracker.available_funds[0].source_type == 'rsu'
        assert 'WDAY' in tracker.positions
        assert tracker.positions['WDAY'].quantity == 100.0
    
    def test_allocate_funds(self):
        """Test fund allocation."""
        tracker = PortfolioFlowTracker()
        # Add some available funds
        fund1 = FundSource('sell', 'AAPL', 1000.0, datetime(2020, 1, 1), 0)
        fund2 = FundSource('sell', 'MSFT', 500.0, datetime(2020, 1, 2), 1)
        tracker.available_funds = [fund1, fund2]
        
        allocations = tracker._allocate_funds(1200.0, 'GOOGL', datetime(2020, 1, 3))
        assert len(allocations) == 2  # AAPL and MSFT (no Initial Cash needed)
        assert allocations[0][1] == 1000.0  # AAPL amount
        assert allocations[1][1] == 200.0   # Part of MSFT amount
    
    def test_create_sankey_diagram(self):
        """Test Sankey diagram creation."""
        tracker = PortfolioFlowTracker()
        # Add some test data
        tracker.node_labels = ["Initial Cash", "AAPL", "MSFT"]
        tracker.node_colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
        tracker.flow_data = [
            {'source': 0, 'target': 1, 'value': 1000.0, 'date': '2020-01-01'},
            {'source': 1, 'target': 2, 'value': 500.0, 'date': '2020-01-02'}
        ]
        
        # Create diagram
        fig = tracker.create_sankey_diagram()
        
        # Check that it's a Plotly figure
        assert hasattr(fig, 'data')
        assert fig.data is not None
        # Check that it contains Sankey data
        assert any('sankey' in str(d).lower() for d in fig.data)
    
    def test_save_diagram(self):
        """Test diagram saving."""
        tracker = PortfolioFlowTracker()
        # Add minimal test data
        tracker.node_labels = ["Initial Cash", "AAPL"]
        tracker.node_colors = ["#1f77b4", "#ff7f0e"]
        tracker.flow_data = [{'source': 0, 'target': 1, 'value': 1000.0, 'date': '2020-01-01'}]
        
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as tmp:
            filename = tmp.name
        
        try:
            tracker.save_diagram(filename)
            assert os.path.exists(filename)
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'sankey' in content.lower()
        finally:
            if os.path.exists(filename):
                os.unlink(filename)


def test_integration():
    """Integration test with sample data."""
    tracker = PortfolioFlowTracker()
    
    # Create sample transactions
    transactions_data = [
        {'transaction': 'buy', 'symbol': 'AAPL', 'date': '2020-01-01', 'quantity': 10, 'price': 150, 'source': 'Funds'},
        {'transaction': 'sell', 'symbol': 'AAPL', 'date': '2020-02-01', 'quantity': 5, 'price': 160, 'source': 'Funds'},
        {'transaction': 'buy', 'symbol': 'MSFT', 'date': '2020-03-01', 'quantity': 8, 'price': 200, 'source': 'Funds'},
        {'transaction': 'buy', 'symbol': 'WDAY', 'date': '2020-04-01', 'quantity': 50, 'price': 180, 'source': 'RSU'},
    ]
    
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        df = pd.DataFrame(transactions_data)
        df.to_csv(tmp.name, index=False)
        filename = tmp.name
    
    try:
        # Process transactions
        tracker.process_transactions(filename)
        
        # Check results
        assert len(tracker.node_labels) > 1
        assert len(tracker.flow_data) > 0
        assert 'AAPL' in tracker.positions
        assert 'MSFT' in tracker.positions
        assert 'WDAY' in tracker.positions
        
        # Check that RSU transaction was processed correctly
        rsu_flows = [f for f in tracker.flow_data if 'RSU Compensation' in [tracker.node_labels[f['source']], tracker.node_labels[f['target']]]]
        assert len(rsu_flows) > 0
        
    finally:
        if os.path.exists(filename):
            os.unlink(filename)


if __name__ == "__main__":
    pytest.main([__file__]) 