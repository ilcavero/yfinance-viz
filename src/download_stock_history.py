import pandas as pd
import yfinance as yf
import os
from datetime import date, timedelta
import traceback


def get_ticker_info(ticker_symbol):
    """Fetches ticker information from yfinance."""
    ticker = yf.Ticker(ticker_symbol)
    return ticker.info


def get_stock_history(ticker_symbol, start_date, end_date):
    """Fetches historical stock data from yfinance."""
    ticker = yf.Ticker(ticker_symbol)
    # auto_adjust=False is required to get 'Stock Splits'
    return ticker.history(start=start_date, end=end_date, auto_adjust=False)


def get_start_date(output_csv, transactions_df, ticker_symbol):
    """
    Determines the start date for fetching data.
    If existing data is found, it returns the day after the last entry.
    Otherwise, it returns the earliest transaction date for the ticker.
    """
    if os.path.exists(output_csv):
        try:
            existing_df = pd.read_csv(output_csv, parse_dates=['Date'])
            if not existing_df.empty:
                last_date = existing_df['Date'].max().date()
                print(f"Existing data found for {ticker_symbol} up to {last_date}.")
                return last_date + timedelta(days=1)
        except (pd.errors.EmptyDataError, KeyError, FileNotFoundError):
            print(f"Warning: {output_csv} is empty or invalid. Will download from the beginning.")

    return transactions_df[transactions_df['symbol'] == ticker_symbol]['date'].min().date()


def update_stock_data(ticker_symbol, start_date, resources_path):
    """
    Fetches and saves stock data for a given ticker and start date.
    
    Args:
        ticker_symbol (str): The stock ticker symbol
        start_date (str or date): Start date for fetching data. Can be a string in 'YYYY-MM-DD' format or a date object
        resources_path (str): Path to the resources directory where CSV files will be saved. 
                             If relative path, will be resolved relative to the script's location.
    """
    # If resources_path is relative, make it relative to the script's location
    if not os.path.isabs(resources_path):
        base_path = os.path.dirname(__file__)
        resources_path = os.path.join(base_path, resources_path)
    
    # Create resources directory if it doesn't exist
    if not os.path.exists(resources_path):
        os.makedirs(resources_path)
    
    output_csv = os.path.join(resources_path, f"{ticker_symbol}.csv")
    today = date.today()
    
    # Parse start_date if it's a string, otherwise use as-is (for backward compatibility)
    if isinstance(start_date, str):
        try:
            start_date = pd.to_datetime(start_date).date()
        except ValueError as e:
            print(f"Invalid date format for {ticker_symbol}. Expected 'YYYY-MM-DD' format. Error: {e}\n")
            return
    elif not isinstance(start_date, date):
        print(f"Invalid start_date type for {ticker_symbol}. Expected string or date object.\n")
        return

    if start_date >= today:
        print(f"Stock {ticker_symbol} is already up to date. Skipping.\n")
        return

    print(f"Fetching data for {ticker_symbol} from {start_date} to {today}...")

    try:
        history_df = get_stock_history(ticker_symbol, start_date.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))



        if history_df.empty:
            print(f"No new data found for {ticker_symbol}.\n")
            return

        info = get_ticker_info(ticker_symbol)
        currency = info.get('currency', 'N/A')
        print(f"Currency for {ticker_symbol}: {currency}")

        history_df['Currency'] = currency
        output_df = history_df[['Close', 'Stock Splits', 'Currency']]

        should_write_header = not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0
        write_df_to_csv(output_df, output_csv, mode='a', header=should_write_header, index=False)

        print(f"Successfully updated {ticker_symbol}.csv\n")

    except Exception as e:
        print(f"Could not download data for {ticker_symbol}. Error: {e}\n")
        traceback.print_exc()


def write_df_to_csv(df, *args, **kwargs):
    return df.to_csv(*args, **kwargs)


def download_stock_history():
    """
    Downloads and updates daily stock price history for tickers in transactions.csv.
    """
    base_path = os.path.dirname(__file__)
    resources_path = os.path.join(base_path, 'resources')
    transactions_file = os.path.join(resources_path, 'transactions.csv')

    if not os.path.exists(resources_path):
        os.makedirs(resources_path)

    try:
        transactions_df = pd.read_csv(transactions_file, parse_dates=['date'])
    except FileNotFoundError:
        print(f"Error: The file {transactions_file} was not found.")
        return

    unique_tickers = transactions_df['symbol'].unique()
    
    # Ensure EURUSD=X is always included for currency conversion
    if 'EURUSD=X' not in unique_tickers:
        unique_tickers = list(unique_tickers) + ['EURUSD=X']
        print("Added EURUSD=X to download list for currency conversion.")
    
    print(f"Found {len(unique_tickers)} unique tickers. Processing...\n")

    for ticker_symbol in unique_tickers:
        print(f"-- Processing {ticker_symbol} --")
        output_csv = os.path.join(resources_path, f"{ticker_symbol}.csv")
        
        # For EURUSD=X, use a default start date if not in transactions
        if ticker_symbol == 'EURUSD=X' and ticker_symbol not in transactions_df['symbol'].values:
            # Use a reasonable default start date (e.g., 2 years ago)
            default_start_date = date.today() - timedelta(days=730)
            start_date = get_start_date(output_csv, transactions_df, ticker_symbol) if os.path.exists(output_csv) else default_start_date
        else:
            start_date = get_start_date(output_csv, transactions_df, ticker_symbol)
        
        update_stock_data(ticker_symbol, start_date, resources_path)


if __name__ == "__main__":
    download_stock_history()