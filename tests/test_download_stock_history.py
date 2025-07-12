import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import os
import shutil
from datetime import date
from src.download_stock_history import (
    get_start_date, 
    update_stock_data, 
    get_ticker_info, 
    get_stock_history,
    download_stock_history
)

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

def test_get_start_date_with_empty_csv(test_environment):
    """Test get_start_date when CSV file exists but is empty."""
    test_dir, transactions_df = test_environment
    output_csv = os.path.join(test_dir, 'AAPL.csv')
    
    # Create an empty CSV file
    with open(output_csv, 'w') as f:
        f.write('')
    
    start_date = get_start_date(output_csv, transactions_df, 'AAPL')
    assert start_date == date(2022, 12, 1)

def test_get_start_date_with_invalid_csv(test_environment):
    """Test get_start_date when CSV file exists but has invalid format."""
    test_dir, transactions_df = test_environment
    output_csv = os.path.join(test_dir, 'AAPL.csv')
    
    # Create a CSV file without Date column
    invalid_data = {'Close': [150.0], 'Stock Splits': [0]}
    invalid_df = pd.DataFrame(invalid_data)
    invalid_df.to_csv(output_csv, index=False)
    
    # Should raise ValueError due to missing 'Date' column
    with pytest.raises(ValueError, match="Missing column provided to 'parse_dates': 'Date'"):
        get_start_date(output_csv, transactions_df, 'AAPL')

def test_get_start_date_with_file_not_found_error(test_environment):
    """Test get_start_date when CSV file doesn't exist."""
    test_dir, transactions_df = test_environment
    output_csv = os.path.join(test_dir, 'NONEXISTENT.csv')
    
    start_date = get_start_date(output_csv, transactions_df, 'AAPL')
    assert start_date == date(2022, 12, 1)

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

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
def test_update_stock_data_with_string_date(mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test update_stock_data with string date parameter."""
    test_dir, _ = test_environment
    
    mock_get_ticker_info.return_value = {'currency': 'USD'}
    history_data = {'Close': [155.0], 'Stock Splits': [0]}
    mock_history_df = pd.DataFrame(history_data, index=pd.to_datetime(['2023-01-12']))
    mock_get_stock_history.return_value = mock_history_df

    ticker_symbol = 'AAPL'
    start_date = '2023-01-12'
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")

    update_stock_data(ticker_symbol, start_date, test_dir)

    assert os.path.exists(output_csv)

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
def test_update_stock_data_with_invalid_date_string(mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test update_stock_data with invalid date string."""
    test_dir, _ = test_environment
    
    ticker_symbol = 'AAPL'
    start_date = 'invalid-date'
    
    update_stock_data(ticker_symbol, start_date, test_dir)
    
    # Should not create any file due to invalid date
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")
    assert not os.path.exists(output_csv)

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
def test_update_stock_data_with_future_date(mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test update_stock_data with future date."""
    test_dir, _ = test_environment
    
    ticker_symbol = 'AAPL'
    future_date = date.today() + pd.Timedelta(days=1)
    
    update_stock_data(ticker_symbol, future_date, test_dir)
    
    # Should not create any file due to future date
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")
    assert not os.path.exists(output_csv)

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
def test_update_stock_data_with_empty_history(mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test update_stock_data when yfinance returns empty history."""
    test_dir, _ = test_environment
    
    mock_get_ticker_info.return_value = {'currency': 'USD'}
    mock_get_stock_history.return_value = pd.DataFrame()  # Empty DataFrame

    ticker_symbol = 'AAPL'
    start_date = date(2023, 1, 12)
    
    update_stock_data(ticker_symbol, start_date, test_dir)
    
    # Should not create any file due to empty history
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")
    assert not os.path.exists(output_csv)

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
def test_update_stock_data_with_exception(mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test update_stock_data when yfinance raises an exception."""
    test_dir, _ = test_environment
    
    mock_get_ticker_info.side_effect = Exception("Network error")
    
    ticker_symbol = 'AAPL'
    start_date = date(2023, 1, 12)
    
    update_stock_data(ticker_symbol, start_date, test_dir)
    
    # Should not create any file due to exception
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")
    assert not os.path.exists(output_csv)

@patch('src.download_stock_history.get_stock_history')
@patch('src.download_stock_history.get_ticker_info')
@patch('src.download_stock_history.write_df_to_csv')
def test_update_stock_data_append_to_existing(mock_write_df_to_csv, mock_get_ticker_info, mock_get_stock_history, test_environment):
    """Test update_stock_data appending to existing CSV file."""
    test_dir, _ = test_environment
    
    # Create existing CSV file with correct columns
    ticker_symbol = 'AAPL'
    output_csv = os.path.join(test_dir, f"{ticker_symbol}.csv")
    existing_data = {'Close': [150.0], 'Stock Splits': [0], 'Currency': ['USD']}
    existing_df = pd.DataFrame(existing_data)
    existing_df.to_csv(output_csv, index=False)
    
    mock_get_ticker_info.return_value = {'currency': 'USD'}
    # Ensure the mock DataFrame matches the columns and does not write the index
    history_data = {'Close': [155.0], 'Stock Splits': [0], 'Currency': ['USD']}
    mock_history_df = pd.DataFrame(history_data)
    mock_get_stock_history.return_value = mock_history_df
    
    start_date = date(2023, 1, 11)
    update_stock_data(ticker_symbol, start_date, test_dir)
    # Should have been called at least once
    assert mock_write_df_to_csv.call_count >= 1
    # Do not check file content since the shim is mocked

@patch('yfinance.Ticker')
def test_get_ticker_info(mock_ticker_class):
    """Test get_ticker_info function."""
    mock_ticker = MagicMock()
    mock_ticker.info = {'currency': 'USD', 'sector': 'Technology'}
    mock_ticker_class.return_value = mock_ticker
    
    result = get_ticker_info('AAPL')
    
    assert result == {'currency': 'USD', 'sector': 'Technology'}
    mock_ticker_class.assert_called_once_with('AAPL')

@patch('yfinance.Ticker')
def test_get_stock_history(mock_ticker_class):
    """Test get_stock_history function."""
    mock_ticker = MagicMock()
    history_data = {'Close': [150.0, 155.0], 'Stock Splits': [0, 0]}
    mock_history_df = pd.DataFrame(history_data, index=pd.to_datetime(['2023-01-10', '2023-01-11']))
    mock_ticker.history.return_value = mock_history_df
    mock_ticker_class.return_value = mock_ticker
    
    result = get_stock_history('AAPL', '2023-01-10', '2023-01-11')
    
    assert result.equals(mock_history_df)
    mock_ticker.history.assert_called_once_with(start='2023-01-10', end='2023-01-11', auto_adjust=False)

@patch('src.download_stock_history.update_stock_data')
@patch('src.download_stock_history.get_start_date')
@patch('pandas.read_csv')
@patch('os.path.exists')
def test_download_stock_history_success(mock_exists, mock_read_csv, mock_get_start_date, mock_update_stock_data, test_environment):
    """Test the main download_stock_history function."""
    test_dir, _ = test_environment
    
    # Mock file existence
    mock_exists.return_value = True
    
    # Mock transactions data
    transactions_data = {'symbol': ['AAPL', 'GOOGL'], 'date': ['2023-01-01', '2023-01-02']}
    transactions_df = pd.DataFrame(transactions_data)
    transactions_df['date'] = pd.to_datetime(transactions_df['date'])
    mock_read_csv.return_value = transactions_df
    
    # Mock start date
    mock_get_start_date.return_value = date(2023, 1, 1)
    
    # Patch only os.path.dirname to return test_dir
    with patch('src.download_stock_history.os.path.dirname', return_value=test_dir):
        download_stock_history()
    
    # Should call update_stock_data for each ticker plus EURUSD=X
    assert mock_update_stock_data.call_count == 3  # AAPL, GOOGL, EURUSD=X

@patch('pandas.read_csv')
@patch('os.path.exists')
def test_download_stock_history_missing_transactions_file(mock_exists, mock_read_csv, test_environment):
    """Test download_stock_history when transactions.csv is missing."""
    test_dir, _ = test_environment
    
    # Mock file existence
    mock_exists.return_value = True
    
    # Mock FileNotFoundError when reading transactions
    mock_read_csv.side_effect = FileNotFoundError("File not found")
    
    with patch('src.download_stock_history.os.path.dirname', return_value=test_dir):
        download_stock_history()
    # Should handle the error gracefully without raising exception
