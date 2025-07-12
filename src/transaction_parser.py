import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Union

import pandas as pd


def extract_transactions_from_file(file_path: Path) -> Iterator[Dict[str, Any]]:
    """Extracts raw transaction records from a single JSON file."""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        for position in data.get("transactionsByPositionIdsMap", {}).values():
            yield from position.get("transactions", [])
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Warning: Could not process {file_path}. Reason: {e}")
        return


def determine_transaction_source(transaction: Dict[str, Any]) -> str:
    """Determines the source of a buy transaction based on the comment field."""
    if transaction.get("type") != "BUY":
        return "Funds"  # Sell transactions are always from funds
    
    comment = transaction.get("comment", "").upper()
    
    # Check for employment-based compensation
    if "RSU" in comment:
        return "RSU"
    elif "ESPP" in comment:
        return "ESPP"
    elif "PSU" in comment:
        return "PSU"
    else:
        return "Funds"  # Default to funds for cash purchases


def format_transaction(transaction: Dict[str, Any]) -> Union[Dict[str, Any], None]:
    """Formats a single transaction record. Returns None if the record is invalid."""
    required_keys = ["type", "symbol", "date", "quantity", "pricePerShare"]
    if not all(key in transaction for key in required_keys):
        return None

    date_str = str(transaction["date"])
    if len(date_str) != 8 or not date_str.isdigit():
        return None  # Basic validation for YYYYMMDD format

    formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    return {
        "transaction": transaction["type"].lower(),
        "symbol": transaction["symbol"],
        "date": formatted_date,
        "quantity": transaction["quantity"],
        "price": transaction.get("pricePerShare"),
        "source": determine_transaction_source(transaction),
    }


def prompt_user_for_file(file_path: Path) -> bool:
    """Prompts the user whether to process a specific JSON file. Defaults to yes."""
    while True:
        response = input(f"Process {file_path.name}? (Y/n): ").strip().lower()
        if response in ['y', 'yes', '']:  # Empty string defaults to yes
            return True
        elif response in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' for yes, 'n' for no, or press Enter for yes (default).")


def process_transactions(resource_dir: Path) -> List[Dict[str, Any]]:
    """Processes JSON files in a directory and returns a list of formatted transactions.
    Prompts the user for each JSON file found."""
    all_formatted_transactions = []
    json_files = list(resource_dir.glob("*.json"))
    
    if not json_files:
        print("No JSON files found in the resources directory.")
        return all_formatted_transactions
    
    print(f"Found {len(json_files)} JSON file(s) in the resources directory.")
    
    for json_file in json_files:
        if prompt_user_for_file(json_file):
            print(f"Processing {json_file.name}...")
            for raw_tx in extract_transactions_from_file(json_file):
                formatted_tx = format_transaction(raw_tx)
                if formatted_tx:
                    all_formatted_transactions.append(formatted_tx)
            print(f"Completed processing {json_file.name}")
        else:
            print(f"Skipping {json_file.name}")
    
    return all_formatted_transactions


def write_csv(transactions: List[Dict[str, Any]], output_path: Path) -> None:
    """Writes a list of transactions to a CSV file."""
    if not transactions:
        print("No transactions to write.")
        return

    df = pd.DataFrame(transactions)
    columns = ["transaction", "symbol", "date", "quantity", "price", "source"]
    df = df[columns]
    
    # Sort by date (ascending order - oldest first)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')  # Convert back to string format
    
    df.to_csv(output_path, index=False)
    print(f"Successfully created {output_path}")


def transaction_parser() -> int:
    """Main function to run the transaction parsing and CSV generation."""
    base_dir = Path(__file__).parent.parent
    resources_path = base_dir / "src" / "resources"
    output_csv_path = resources_path / "transactions.csv"

    processed_data = process_transactions(resources_path)
    write_csv(processed_data, output_csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(transaction_parser())
