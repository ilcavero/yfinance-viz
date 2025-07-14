import json
import sys
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add yfinance_viz module to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from yfinance_viz.transaction_parser import (
    extract_transactions_from_file,
    format_transaction,
    process_transactions,
    write_csv,
    determine_transaction_source,
    transaction_parser,
)

# Mock data for testing
MOCK_VALID_TRANSACTION = {
    "id": "tx_1",
    "positionId": "pos_1",
    "symbol": "AAPL",
    "type": "BUY",
    "date": 20230115,
    "quantity": 10,
    "pricePerShare": 150.0,
    "commission": 1.99,
    "totalValue": 1501.99,
}

MOCK_INVALID_TRANSACTION = {
    "id": "tx_2",
    "symbol": "GOOG",
    "date": 20230116,
    # Missing 'type', 'quantity', 'pricePerShare'
}

MOCK_JSON_CONTENT = {
    "transactionsByPositionIdsMap": {
        "pos_1": {
            "transactions": [MOCK_VALID_TRANSACTION, MOCK_INVALID_TRANSACTION]
        }
    }
}

@pytest.fixture
def mock_resources_dir(tmp_path: Path) -> Path:
    """Creates a temporary resources directory with mock JSON files for testing."""
    resources_dir = tmp_path / "resources"
    resources_dir.mkdir()
    
    # Create a valid JSON file
    with open(resources_dir / "valid_transactions.json", "w") as f:
        json.dump(MOCK_JSON_CONTENT, f)

    # Create an empty JSON file
    with open(resources_dir / "empty.json", "w") as f:
        json.dump({}, f)

    # Create a malformed JSON file
    with open(resources_dir / "malformed.json", "w") as f:
        f.write("this is not json")
        
    return resources_dir


def test_format_transaction_valid():
    """Tests that a valid transaction is formatted correctly."""
    formatted = format_transaction(MOCK_VALID_TRANSACTION)
    assert formatted is not None
    assert formatted['transaction'] == 'buy'
    assert formatted['symbol'] == 'AAPL'
    assert formatted['date'] == '2023-01-15'
    assert formatted['quantity'] == 10
    assert formatted['price'] == 150.0

def test_format_transaction_invalid_missing_keys():
    """Tests that a transaction with missing keys is handled correctly."""
    assert format_transaction(MOCK_INVALID_TRANSACTION) is None

def test_format_transaction_invalid_date():
    """Tests that a transaction with an invalid date is handled correctly."""
    invalid_date_tx = MOCK_VALID_TRANSACTION.copy()
    invalid_date_tx['date'] = 202301 # Invalid date format
    assert format_transaction(invalid_date_tx) is None

def test_format_transaction_with_comment():
    """Tests that a transaction with comment field is handled correctly."""
    tx_with_comment = MOCK_VALID_TRANSACTION.copy()
    tx_with_comment['comment'] = 'RSU Grant'
    formatted = format_transaction(tx_with_comment)
    assert formatted is not None
    assert formatted['source'] == 'RSU'

def test_extract_transactions_from_file(mock_resources_dir: Path):
    """Tests extraction of transactions from a single file."""
    file_path = mock_resources_dir / "valid_transactions.json"
    transactions = list(extract_transactions_from_file(file_path))
    assert len(transactions) == 2
    assert transactions[0]['symbol'] == 'AAPL'

def test_extract_transactions_from_empty_file(mock_resources_dir: Path):
    """Tests extraction from empty JSON file."""
    file_path = mock_resources_dir / "empty.json"
    transactions = list(extract_transactions_from_file(file_path))
    assert len(transactions) == 0

def test_extract_transactions_from_malformed_file(mock_resources_dir: Path):
    """Tests extraction from malformed JSON file."""
    file_path = mock_resources_dir / "malformed.json"
    transactions = list(extract_transactions_from_file(file_path))
    assert len(transactions) == 0

def test_extract_transactions_from_nonexistent_file(mock_resources_dir: Path):
    """Tests extraction from non-existent file."""
    file_path = mock_resources_dir / "nonexistent.json"
    transactions = list(extract_transactions_from_file(file_path))
    assert len(transactions) == 0

@patch('yfinance_viz.transaction_parser.prompt_user_for_file')
def test_process_transactions(mock_prompt, mock_resources_dir: Path):
    """Tests processing of all transaction files in a directory."""
    # Mock user input to always return True
    mock_prompt.return_value = True
    
    processed = process_transactions(mock_resources_dir)
    assert len(processed) == 1 # Only one transaction is valid
    assert processed[0]['symbol'] == 'AAPL'

@patch('yfinance_viz.transaction_parser.prompt_user_for_file')
def test_process_transactions_user_skips_files(mock_prompt, mock_resources_dir: Path):
    """Tests processing when user skips all files."""
    # Mock user input to always return False
    mock_prompt.return_value = False
    
    processed = process_transactions(mock_resources_dir)
    assert len(processed) == 0

def test_process_transactions_no_json_files(tmp_path: Path):
    """Tests processing when no JSON files exist."""
    processed = process_transactions(tmp_path)
    assert len(processed) == 0

def test_write_csv(tmp_path: Path):
    """Tests that the CSV file is written correctly."""
    output_csv = tmp_path / "output.csv"
    transactions = [
        {
            'transaction': 'buy',
            'symbol': 'AAPL',
            'date': '2023-01-15',
            'quantity': 10,
            'price': 150.0,
            'source': 'Funds'
        }
    ]
    write_csv(transactions, output_csv)
    
    assert output_csv.exists()
    df = pd.read_csv(output_csv)
    assert len(df) == 1
    assert df.iloc[0]['symbol'] == 'AAPL'

def test_write_csv_empty_transactions(tmp_path: Path):
    """Tests write_csv with empty transactions list."""
    output_csv = tmp_path / "output.csv"
    write_csv([], output_csv)
    
    # Should not create file for empty transactions
    assert not output_csv.exists()

def test_write_csv_multiple_transactions(tmp_path: Path):
    """Tests write_csv with multiple transactions."""
    output_csv = tmp_path / "output.csv"
    transactions = [
        {
            'transaction': 'buy',
            'symbol': 'AAPL',
            'date': '2023-01-15',
            'quantity': 10,
            'price': 150.0,
            'source': 'Funds'
        },
        {
            'transaction': 'sell',
            'symbol': 'GOOGL',
            'date': '2023-01-10',
            'quantity': 5,
            'price': 200.0,
            'source': 'Funds'
        }
    ]
    write_csv(transactions, output_csv)
    
    assert output_csv.exists()
    df = pd.read_csv(output_csv)
    assert len(df) == 2
    # Should be sorted by date (oldest first)
    assert df.iloc[0]['date'] == '2023-01-10'
    assert df.iloc[1]['date'] == '2023-01-15'

def test_determine_transaction_source_buy_funds():
    """Test determine_transaction_source for regular buy transaction."""
    transaction = {'type': 'BUY', 'comment': 'Regular purchase'}
    source = determine_transaction_source(transaction)
    assert source == 'Funds'

def test_determine_transaction_source_buy_rsu():
    """Test determine_transaction_source for RSU transaction."""
    transaction = {'type': 'BUY', 'comment': 'RSU Grant 2023'}
    source = determine_transaction_source(transaction)
    assert source == 'RSU'

def test_determine_transaction_source_buy_espp():
    """Test determine_transaction_source for ESPP transaction."""
    transaction = {'type': 'BUY', 'comment': 'ESPP Purchase'}
    source = determine_transaction_source(transaction)
    assert source == 'ESPP'

def test_determine_transaction_source_buy_psu():
    """Test determine_transaction_source for PSU transaction."""
    transaction = {'type': 'BUY', 'comment': 'PSU Award'}
    source = determine_transaction_source(transaction)
    assert source == 'PSU'

def test_determine_transaction_source_sell():
    """Test determine_transaction_source for sell transaction."""
    transaction = {'type': 'SELL', 'comment': 'Any comment'}
    source = determine_transaction_source(transaction)
    assert source == 'Funds'

def test_determine_transaction_source_no_comment():
    """Test determine_transaction_source with no comment field."""
    transaction = {'type': 'BUY'}
    source = determine_transaction_source(transaction)
    assert source == 'Funds'

def test_determine_transaction_source_case_insensitive():
    """Test determine_transaction_source with case insensitive matching."""
    transaction = {'type': 'BUY', 'comment': 'rsu grant'}
    source = determine_transaction_source(transaction)
    assert source == 'RSU'

@patch('yfinance_viz.transaction_parser.process_transactions')
@patch('yfinance_viz.transaction_parser.write_csv')
@patch('yfinance_viz.transaction_parser.Path')
def test_transaction_parser_success(mock_path, mock_write_csv, mock_process_transactions):
    """Test the main transaction_parser function."""
    # Mock the path operations
    mock_resources_path = MagicMock()
    mock_output_path = MagicMock()
    
    mock_path.return_value = mock_resources_path
    mock_resources_path.__truediv__.return_value = mock_output_path
    
    # Mock process_transactions to return some data
    mock_process_transactions.return_value = [{'transaction': 'buy', 'symbol': 'AAPL'}]
    
    result = transaction_parser("/test/resources")
    
    assert result == 0
    mock_process_transactions.assert_called_once_with(mock_resources_path)
    mock_write_csv.assert_called_once_with([{'transaction': 'buy', 'symbol': 'AAPL'}], mock_output_path)

@patch('yfinance_viz.transaction_parser.process_transactions')
@patch('yfinance_viz.transaction_parser.write_csv')
@patch('yfinance_viz.transaction_parser.Path')
def test_transaction_parser_empty_transactions(mock_path, mock_write_csv, mock_process_transactions):
    """Test transaction_parser with empty transactions."""
    # Mock the path operations
    mock_resources_path = MagicMock()
    mock_output_path = MagicMock()
    
    mock_path.return_value = mock_resources_path
    mock_resources_path.__truediv__.return_value = mock_output_path
    
    # Mock process_transactions to return empty list
    mock_process_transactions.return_value = []
    
    result = transaction_parser("/test/resources")
    
    assert result == 0
    mock_write_csv.assert_called_once_with([], mock_output_path)
