import pytest
from unittest.mock import patch
import pandas as pd
import os
import shutil
from datetime import date
from src.download_stock_history import get_start_date, update_stock_data

@pytest.fixture
def test_environment(tmpdir):
    """Create a temporary directory and dummy data for tests."""
    test_dir = str(tmpdir.mkdir("test_resources"))
    
    # Create a dummy transactions.csv
    transactions_data = {'symbol': ['AAPL', 'GOOGL', 'AAPL'], 'date': ['2023-01-01', '2023-01-02', '2022-12-01']}
    transactions_df = pd.DataFrame(transactions_data)
    transactions_df['date'] = pd.to_datetime(transactions_df['date'])
    
    yield test_dir, transactions_df

    # Cleanup is handled by tmpdir fixture

def test_get_start_date_no_existing_file(test_environment):
    """Test get_start_date when no CSV file exists for the ticker."""
    test_dir, transactions_df = test_environment
    output_csv = os.path.join(test_dir, 'AAPL.csv')
    start_date = get_start_date(output_csv, transactions_df, 'AAPL')
    assert start_date == date(2022, 12, 1)

def test_get_start_date_with_existing_file(test_environment):
    """Test get_start_date when a CSV file already exists."""
    test_dir, transactions_df = test_environment
    output_csv = os.path.join(test_dir, 'AAPL.csv')
    
    # Create a dummy existing CSV for AAPL
    existing_data = {'Date': ['2023-01-10'], 'Close': [150.0], 'Stock Splits': [0], 'Currency': ['USD']}
    existing_df = pd.DataFrame(existing_data)
    existing_df['Date'] = pd.to_datetime(existing_df['Date'])
    existing_df.to_csv(output_csv, index=False)

    start_date = get_start_date(output_csv, transactions_df, 'AAPL')
    assert start_date == date(2023, 1, 11)

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
def test_update_stock_data(mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test the complete update_stock_data function with mocked yfinance calls."""
    test_dir, _ = test_environment
    
    # Mock the return values from yfinance functions
    mock_get_ticker_info.return_value = {'currency': 'USD'}
    
    history_data = {'Close': [155.0], 'Stock Splits': [0]}
    mock_history_df = pd.DataFrame(history_data, index=pd.to_datetime(['2023-01-12']))
    mock_get_stock_history.return_value = mock_history_df

    # Define parameters for the function call
    ticker_symbol = 'AAPL'
    start_date = date(2023, 1, 12)
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")

    # Call the function to be tested
    update_stock_data(ticker_symbol, start_date, test_dir)

    # Assert that the CSV was created and contains the correct data
    assert os.path.exists(output_csv)
    result_df = pd.read_csv(output_csv)
    assert result_df.shape[0] == 1
    assert result_df['Close'][0] == 155.0
    assert result_df['Currency'][0] == 'USD'
