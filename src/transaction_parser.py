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
    }


def process_transactions(resource_dir: Path) -> List[Dict[str, Any]]:
    """Processes all JSON files in a directory and returns a list of formatted transactions."""
    all_formatted_transactions = []
    for json_file in resource_dir.glob("*.json"):
        for raw_tx in extract_transactions_from_file(json_file):
            formatted_tx = format_transaction(raw_tx)
            if formatted_tx:
                all_formatted_transactions.append(formatted_tx)
    return all_formatted_transactions


def write_csv(transactions: List[Dict[str, Any]], output_path: Path) -> None:
    """Writes a list of transactions to a CSV file."""
    if not transactions:
        print("No transactions to write.")
        return

    df = pd.DataFrame(transactions)
    columns = ["transaction", "symbol", "date", "quantity", "price"]
    df = df[columns]
    df.to_csv(output_path, index=False)
    print(f"Successfully created {output_path}")


def transaction_parser() -> int:
    """Main function to run the transaction parsing and CSV generation."""
    base_dir = Path(__file__).parent.parent
    resources_path = base_dir / "src" / "resources"
    output_csv_path = base_dir / "transactions.csv"

    processed_data = process_transactions(resources_path)
    write_csv(processed_data, output_csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(transaction_parser())
