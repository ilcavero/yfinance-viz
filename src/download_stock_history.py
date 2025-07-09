import pandas as pd
import yfinance as yf
import os
from datetime import date, timedelta

def download_stock_history():
    """
    Downloads and updates daily stock price history for tickers in transactions.csv.

    For each unique ticker, it fetches the daily close price and stock splits
    from the earliest transaction date until today. It stores the data in a
    separate CSV file for each ticker in the 'resources' directory.

    The script supports incremental updates, avoiding re-downloading data that
    already exists in the output CSVs.
    """
    # Define paths relative to the script's location
    base_path = os.path.dirname(__file__)
    resources_path = os.path.join(base_path, 'resources')
    transactions_file = os.path.join(resources_path, 'transactions.csv')
    
    # Ensure output directory exists
    if not os.path.exists(resources_path):
        os.makedirs(resources_path)

    # 1. Read transactions and find unique tickers
    try:
        transactions_df = pd.read_csv(transactions_file, parse_dates=['date'])
    except FileNotFoundError:
        print(f"Error: The file {transactions_file} was not found.")
        return

    unique_tickers = transactions_df['symbol'].unique()
    today = date.today()

    print(f"Found {len(unique_tickers)} unique tickers. Processing...\n")

    # 2. Process each ticker
    for ticker_symbol in unique_tickers:
        print(f"-- Processing {ticker_symbol} --")
        output_csv = os.path.join(resources_path, f"{ticker_symbol}.csv")

        # Determine the absolute start date from all transactions for this ticker
        start_date = transactions_df[transactions_df['symbol'] == ticker_symbol]['date'].min().date()

        # 3. Efficiency - Incremental update check
        if os.path.exists(output_csv):
            try:
                existing_df = pd.read_csv(output_csv, parse_dates=['Date'])
                if not existing_df.empty:
                    last_date = existing_df['Date'].max().date()
                    print(f"Existing data found for {ticker_symbol} up to {last_date}.")
                    # Set start date to the day after the last recorded date
                    start_date = last_date + timedelta(days=1)
            except (pd.errors.EmptyDataError, KeyError, FileNotFoundError):
                print(f"Warning: {output_csv} is empty or invalid. Will download from the beginning.")

        if start_date >= today:
            print(f"Stock {ticker_symbol} is already up to date. Skipping.\n")
            continue

        print(f"Fetching data for {ticker_symbol} from {start_date} to {today}...")

        # 4. Fetch data from yfinance
        ticker = yf.Ticker(ticker_symbol)
        try:
            # auto_adjust=False is required to get 'Stock Splits'
            history_df = ticker.history(start=start_date.strftime('%Y-%m-%d'), end=today.strftime('%Y-%m-%d'), auto_adjust=False)

            if history_df.empty:
                print(f"No new data found for {ticker_symbol}.\n")
                continue

            # Fetch currency from the ticker info
            currency = ticker.info.get('currency', 'N/A')
            print(f"Currency for {ticker_symbol}: {currency}")

            # 5. Prepare data for output
            history_df['Currency'] = currency
            output_df = history_df[['Close', 'Stock Splits', 'Currency']]

            # 6. Output data to CSV
            # Write header only if the file is new or empty
            should_write_header = not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0
            output_df.to_csv(output_csv, mode='a', header=should_write_header)

            print(f"Successfully updated {ticker_symbol}.csv\n")

        except Exception as e:
            print(f"Could not download data for {ticker_symbol}. Error: {e}\n")

if __name__ == "__main__":
    download_stock_history()