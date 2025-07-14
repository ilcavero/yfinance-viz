# yfinance-viz

**Yahoo Finance Portfolio Visualizer** - A Python tool for downloading and visualizing stock portfolio transactions using Yahoo Finance data.

## Features

- **Transaction Parser**: Converts Yahoo Finance portfolio JSON exports to CSV format
- **Stock History Downloader**: Automatically downloads historical stock data for portfolio tickers
- **Portfolio Visualization**: Creates interactive Sankey diagrams showing fund flows between positions
- **Multi-currency Support**: Handles USD/EUR conversions automatically
- **Command-Line Tools**: Easy-to-use CLI commands for all functionality

## Installation

```bash
pip install yfinance-viz
```

## Usage

### Using CLI Commands

After installation, you can use the convenient CLI commands:

```bash
# Parse transactions from your portfolio data directory
yfinance-viz-parse --resources-path /path/to/my/portfolio/data

# Download stock history to your portfolio data directory
yfinance-viz-download --resources-path /path/to/my/portfolio/data

# Generate visualization from your portfolio data directory
yfinance-viz-visualize --resources-path /path/to/my/portfolio/data
```

### Workflow

#### 1. Export Your Portfolio Data

Determine your portafolio ID by going to and looking for the p_0 or similar in the path when opening the portafolio in:
``` 
https://finance.yahoo.com/portfolios/
```

Download your portfolio transactions from Yahoo Finance:
```
https://query1.finance.yahoo.com/ws/portfolio-api/v1/portfolio/transactions?pfId=YOUR_PORTFOLIO_ID&category=trades&groupByPositionId=true&lang=en-US&region=US
```

Save the JSON file in your chosen resources directory (e.g., `my_portfolio_data/my_portfolio.json`).

#### 2. Parse Transactions

```bash
yfinance-viz-parse --resources-path /path/to/my/portfolio/data
```

This will:
- Prompt you to select which JSON files to process
- Convert transactions to CSV format
- Save as `transactions.csv` in your resources directory

#### 3. Download Stock History

```bash
yfinance-viz-download --resources-path /path/to/my/portfolio/data
```

Downloads historical price data for all tickers in your transactions.

#### 4. Generate Visualization

```bash
yfinance-viz-visualize --resources-path /path/to/my/portfolio/data
```

Creates an interactive Sankey diagram showing fund flows between your portfolio positions.

## Project Structure

```
yfinance-viz/
├── yfinance_viz/           # Main module
│   ├── __init__.py
│   ├── transaction_parser.py
│   ├── download_stock_history.py
│   └── transactions_visualize.py
├── tests/                  # Comprehensive test suite
├── pyproject.toml         # Project configuration
└── README.md
```

## Command-Line Options

All scripts **require** the following argument:

- `--resources-path`: Path to the directory containing your portfolio data
  - **Required**: This argument must be provided
  - Example: `--resources-path /Users/john/my_portfolio_data`

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=yfinance_viz
```

## Privacy

- All personal portfolio data should be stored in your chosen resources directory
- The tool processes local files only - no data is sent to external services

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.