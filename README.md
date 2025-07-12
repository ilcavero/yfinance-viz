# YFinance Portfolio Manager

A Python tool for downloading and visualizing stock portfolio transactions using Yahoo Finance data.

## Features

- **Transaction Parser**: Converts Yahoo Finance portfolio JSON exports to CSV format
- **Stock History Downloader**: Automatically downloads historical stock data for portfolio tickers
- **Portfolio Visualization**: Creates interactive Sankey diagrams showing fund flows between positions
- **Multi-currency Support**: Handles USD/EUR conversions automatically

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd yfinancemgr

# Install dependencies using uv
uv sync
```

## Usage

### 1. Export Your Portfolio Data

Download your portfolio transactions from Yahoo Finance:
```
https://query1.finance.yahoo.com/ws/portfolio-api/v1/portfolio/transactions?pfId=YOUR_PORTFOLIO_ID&category=trades&groupByPositionId=true&lang=en-US&region=US
```

Save the JSON file in `src/resources/` with a descriptive name (e.g., `my_portfolio.json`).

### 2. Parse Transactions

```bash
# Activate environment and run parser
uv run python src/transaction_parser.py
```

This will:
- Prompt you to select which JSON files to process
- Convert transactions to CSV format
- Save as `src/resources/transactions.csv`

### 3. Download Stock History

```bash
uv run python src/download_stock_history.py
```

Downloads historical price data for all tickers in your transactions.

### 4. Generate Visualization

```bash
uv run python src/transactions_visualize.py
```

Creates an interactive Sankey diagram showing fund flows between your portfolio positions.

## Project Structure

```
yfinancemgr/
├── src/
│   ├── resources/          # Your portfolio data (not in git)
│   ├── download_stock_history.py
│   ├── transaction_parser.py
│   └── transactions_visualize.py
├── tests/                  # Comprehensive test suite
├── pyproject.toml         # Project configuration
└── README.md
```

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src
```

## Privacy

- All personal portfolio data should be stored in `src/resources/`
- This directory is excluded from version control
- The tool processes local files only - no data is sent to external services

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.