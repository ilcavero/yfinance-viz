import json
import sys
import pandas as pd
import pytest
from pathlib import Path

# Add src directory to the path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from transaction_parser import (
    extract_transactions_from_file,
    format_transaction,
    process_transactions,
    write_csv,
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

def test_extract_transactions_from_file(mock_resources_dir: Path):
    """Tests extraction of transactions from a single file."""
    file_path = mock_resources_dir / "valid_transactions.json"
    transactions = list(extract_transactions_from_file(file_path))
    assert len(transactions) == 2
    assert transactions[0]['symbol'] == 'AAPL'

def test_process_transactions(mock_resources_dir: Path):
    """Tests processing of all transaction files in a directory."""
    processed = process_transactions(mock_resources_dir)
    assert len(processed) == 1 # Only one transaction is valid
    assert processed[0]['symbol'] == 'AAPL'

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
