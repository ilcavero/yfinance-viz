"""
Stock Portfolio Transaction Sankey Diagram Visualization

This module creates a Sankey diagram showing the flow of funds between different
stock positions in a portfolio, tracking how money moves from sells to buys
and handling currency conversions between USD and EUR. This version uses a single node per stock and displays all values in USD.
"""

import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os
import argparse
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
import numpy as np

@dataclass
class Position:
    symbol: str
    quantity: float
    currency: str
    total_value: float

@dataclass
class FundSource:
    source_type: str  # 'sell', 'cash', 'deposit', 'rsu', 'espp', 'psu'
    symbol: str  # For sells, the symbol being sold
    amount_usd: float  # Amount in USD
    date: datetime
    transaction_id: int

class PortfolioFlowTracker:
    def __init__(self, resources_path: str):
        self.resources_path = resources_path
        self.positions: Dict[str, Position] = {}
        self.available_funds: List[FundSource] = []
        self.flow_data: List[Dict] = []
        self.node_labels: List[str] = []
        self.node_colors: List[str] = []
        self.currency_cache: Dict[str, str] = {}
        self.exchange_rates: Dict[str, float] = {}
        self.node_map: Dict[str, int] = {}  # symbol -> node index
        self.transactions_df: Optional[pd.DataFrame] = None
        self.stock_data_cache: Dict[str, Optional[pd.DataFrame]] = {}
        self._load_exchange_rates()
        self.node_labels = ["Initial Cash"]
        self.node_colors = ["#1f77b4"]
        self.node_map["Initial Cash"] = 0

    def _get_transactions_df(self) -> pd.DataFrame:
        if self.transactions_df is None:
            transactions_file = os.path.join(self.resources_path, "transactions.csv")
            if not os.path.exists(transactions_file):
                self.transactions_df = pd.DataFrame(columns=['symbol', 'transaction', 'date', 'quantity', 'price', 'source'])
            else:
                self.transactions_df = pd.read_csv(transactions_file, parse_dates=["date"])
                self.transactions_df['date'] = self.transactions_df['date'].dt.tz_localize(None)
        return self.transactions_df.copy()

    def _get_stock_data(self, symbol: str) -> Optional[pd.DataFrame]:
        if symbol not in self.stock_data_cache:
            stock_file = os.path.join(self.resources_path, f"{symbol}.csv")
            if not os.path.exists(stock_file):
                self.stock_data_cache[symbol] = None
            else:
                try:
                    df = pd.read_csv(stock_file, index_col='Date', parse_dates=True)
                    assert isinstance(df.index, pd.DatetimeIndex)
                    df.index = df.index.tz_localize(None)
                    self.stock_data_cache[symbol] = df
                except Exception as e:
                    print(f"Warning: Could not load or parse stock data for {symbol}: {e}")
                    self.stock_data_cache[symbol] = None
        
        df = self.stock_data_cache.get(symbol)
        return df.copy() if df is not None else None

    def _load_exchange_rates(self):
        try:
            eurusd_file = os.path.join(self.resources_path, "EURUSD=X.csv")
            eurusd_df = pd.read_csv(eurusd_file, index_col='Date', parse_dates=True)
            assert isinstance(eurusd_df.index, pd.DatetimeIndex)
            eurusd_df.index = eurusd_df.index.tz_localize(None)
            for date, row in eurusd_df.iterrows():
                assert isinstance(date, pd.Timestamp)
                date_str = date.strftime('%Y-%m-%d')
                self.exchange_rates[date_str] = row['Close']
            # Store sorted keys for binary search
            self.sorted_rate_keys = sorted(self.exchange_rates.keys())
        except Exception as e:
            print(f"Warning: Could not load exchange rates: {e}")
            self.sorted_rate_keys = []

    def _find_nearest_exchange_rate(self, target_date_str: str) -> float:
        """Find the nearest exchange rate using binary search on date strings."""
        if not self.sorted_rate_keys:
            raise ValueError("No exchange rates available. EURUSD=X.csv file is empty or could not be loaded.")
        
        # Binary search for the nearest date
        left, right = 0, len(self.sorted_rate_keys) - 1
        
        while left <= right:
            mid = (left + right) // 2
            mid_date_str = self.sorted_rate_keys[mid]
            
            if mid_date_str == target_date_str:
                return self.exchange_rates[mid_date_str]
            elif mid_date_str < target_date_str:
                left = mid + 1
            else:
                right = mid - 1
        
        # Find the closest among the candidates
        candidates = []
        if left < len(self.sorted_rate_keys):
            candidates.append(self.sorted_rate_keys[left])
        if right >= 0:
            candidates.append(self.sorted_rate_keys[right])
        
        if not candidates:
            # Fallback to first available rate
            nearest_key = self.sorted_rate_keys[0]
        else:
            # Find the closest date string
            nearest_key = min(candidates, key=lambda x: abs(int(x.replace('-', '')) - int(target_date_str.replace('-', ''))))
        
        return self.exchange_rates[nearest_key]

    def _get_stock_currency(self, symbol: str) -> str:
        if symbol in self.currency_cache:
            return self.currency_cache[symbol]
        try:
            df = self._get_stock_data(symbol)
            if df is not None and 'Currency' in df.columns and len(df) > 0:
                currency = df.iloc[0]['Currency']
                self.currency_cache[symbol] = currency
                return currency
        except Exception as e:
            print(f"Warning: Could not determine currency for {symbol}: {e}")
        self.currency_cache[symbol] = "USD"
        return "USD"

    def _eur_to_usd(self, amount_eur: float, date: datetime) -> float:
        date_str = date.strftime('%Y-%m-%d')
        if date_str in self.exchange_rates:
            rate = self.exchange_rates[date_str]
            return amount_eur * rate
        else:
            # Find the nearest available exchange rate using binary search
            rate = self._find_nearest_exchange_rate(date_str)
            return amount_eur * rate

    def _to_usd(self, amount: float, from_currency: str, date: datetime) -> float:
        if from_currency == "USD":
            return amount
        elif from_currency == "EUR":
            return self._eur_to_usd(amount, date)
        else:
            print(f"Warning: Could not get latest USD conversion rate for {from_currency} on {date}")
            return amount  # fallback, treat as USD

    def _add_node(self, symbol: str):
        if symbol not in self.node_map:
            self.node_labels.append(symbol)
            color = self._get_node_color(symbol)
            self.node_colors.append(color)
            self.node_map[symbol] = len(self.node_labels) - 1
        return self.node_map[symbol]

    def _get_node_color(self, symbol: str) -> str:
        colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
            "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
            "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5"
        ]
        return colors[hash(symbol) % len(colors)]

    def _process_sell_transaction(self, transaction: pd.Series) -> float:
        symbol = transaction['symbol']
        quantity = transaction['quantity']
        price = transaction['price']
        date = pd.to_datetime(transaction['date'])
        currency = self._get_stock_currency(symbol)
        total_value = quantity * price
        usd_value = self._to_usd(total_value, currency, date)
        

        
        fund_source = FundSource(
            source_type='sell',
            symbol=symbol,
            amount_usd=usd_value,
            date=date,
            transaction_id=len(self.available_funds)
        )
        self.available_funds.append(fund_source)
        if symbol in self.positions:
            self.positions[symbol].quantity -= quantity
            if self.positions[symbol].quantity <= 0:
                del self.positions[symbol]
        return usd_value

    def _process_buy_transaction(self, transaction: pd.Series) -> float:
        symbol = transaction['symbol']
        quantity = transaction['quantity']
        price = transaction['price']
        date = pd.to_datetime(transaction['date'])
        currency = self._get_stock_currency(symbol)
        total_value = quantity * price
        usd_value = self._to_usd(total_value, currency, date)
        

        
        if symbol in self.positions:
            self.positions[symbol].quantity += quantity
            self.positions[symbol].total_value += total_value
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                currency=currency,
                total_value=total_value
            )
        return usd_value

    def _process_employment_transaction(self, transaction: pd.Series) -> float:
        """Process RSU, ESPP, or PSU transactions as new inflows."""
        symbol = transaction['symbol']
        quantity = transaction['quantity']
        price = transaction['price']
        date = pd.to_datetime(transaction['date'])
        source_type = transaction['source'].lower()
        currency = self._get_stock_currency(symbol)
        total_value = quantity * price
        usd_value = self._to_usd(total_value, currency, date)
        
        # Add to available funds as employment compensation
        fund_source = FundSource(
            source_type=source_type,
            symbol=symbol,
            amount_usd=usd_value,
            date=date,
            transaction_id=len(self.available_funds)
        )
        self.available_funds.append(fund_source)
        
        # Update position
        if symbol in self.positions:
            self.positions[symbol].quantity += quantity
            self.positions[symbol].total_value += total_value
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                currency=currency,
                total_value=total_value
            )
        
        return usd_value

    def _allocate_funds(self, required_amount: float, buy_symbol: str, buy_date: datetime) -> List[Tuple[str, float]]:
        allocated = []
        remaining_amount = required_amount
        # Sort by transaction_id to use funds in the order they were added (FIFO)
        self.available_funds.sort(key=lambda x: x.transaction_id)
        funds_to_remove = []
        
        for fund in self.available_funds:
            if remaining_amount <= 0:
                break
            if fund.amount_usd <= remaining_amount:
                # For sell transactions, the source is the stock that was sold
                source_node = fund.symbol if fund.source_type == 'sell' else 'Initial Cash'
                allocated.append((source_node, fund.amount_usd))
                remaining_amount -= fund.amount_usd
                funds_to_remove.append(fund)
            else:
                # For sell transactions, the source is the stock that was sold
                source_node = fund.symbol if fund.source_type == 'sell' else 'Initial Cash'
                allocated.append((source_node, remaining_amount))
                fund.amount_usd -= remaining_amount
                remaining_amount = 0
                break
        for fund in funds_to_remove:
            self.available_funds.remove(fund)
        if remaining_amount > 0:
            allocated.append(('Initial Cash', remaining_amount))
        
        return allocated

    def process_transactions(self, transactions_file: Union[str, None] = None):
        """Process all transactions and build the flow data."""
        df = self._get_transactions_df()

        # Get all unique dates from transactions
        all_dates = set(pd.to_datetime(df['date'].unique()))

        # Get all dividend dates from all stock files mentioned in transactions
        all_symbols = df['symbol'].unique()
        for symbol in all_symbols:
            stock_df = self._get_stock_data(symbol)
            if stock_df is not None and 'Dividends' in stock_df.columns:
                dividend_dates = stock_df[stock_df['Dividends'] > 0].index
                for d_date in dividend_dates:
                    all_dates.add(d_date)
        
        sorted_dates = sorted(list(all_dates))

        # Sort transactions for processing
        df['transaction_type'] = df['transaction'].map({'sell': 0, 'buy': 1})
        df = df.sort_values(['date', 'transaction_type']).reset_index(drop=True)

        for date in sorted_dates:
            # 1. Process transactions for the current date
            day_transactions = df[df['date'] == date]
            for idx, transaction in day_transactions.iterrows():
                transaction_type = transaction['transaction']
                symbol = transaction['symbol']
                source = str(transaction.get('source', '')).upper()
                
                # Add nodes for all symbols first
                self._add_node(symbol)
                
                if transaction_type == 'sell':
                    usd_value = self._process_sell_transaction(transaction)
                elif transaction_type == 'buy' and source in ['RSU', 'ESPP', 'PSU']:
                    usd_value = self._process_buy_transaction(transaction)
                    source_label = f"{source} Compensation"
                    if source_label not in self.node_map:
                        self.node_labels.append(source_label)
                        self.node_colors.append("#2ca02c")
                        self.node_map[source_label] = len(self.node_labels) - 1
                    source_idx = self.node_map[source_label]
                    target_idx = self.node_map[symbol]
                    self.flow_data.append({
                        'source': source_idx, 'target': target_idx, 'value': usd_value,
                        'date': transaction['date'], 'type': source, 'symbol': symbol,
                        'quantity': transaction['quantity'], 'price': transaction['price'],
                        'from_symbol': source_label,
                    })
                elif transaction_type == 'buy':
                    usd_value = self._process_buy_transaction(transaction)
                    allocated = self._allocate_funds(usd_value, symbol, pd.to_datetime(transaction['date']))
                    
                    aggregated_allocations = {}
                    for source_symbol, amount in allocated:
                        if source_symbol not in aggregated_allocations:
                            aggregated_allocations[source_symbol] = 0
                        aggregated_allocations[source_symbol] += amount
                    
                    for source_symbol, total_amount in aggregated_allocations.items():
                        source_idx = self.node_map[source_symbol]
                        target_idx = self.node_map[symbol]
                        self.flow_data.append({
                            'source': source_idx, 'target': target_idx, 'value': total_amount,
                            'date': transaction['date'], 'type': 'Funds', 'symbol': symbol,
                            'quantity': transaction['quantity'], 'price': transaction['price'],
                            'from_symbol': source_symbol,
                        })
            
            # 2. Process dividends for the current date
            for symbol in self.positions.keys():
                stock_df = self._get_stock_data(symbol)
                if stock_df is None or 'Dividends' not in stock_df.columns:
                    continue
                
                if date in stock_df.index:
                    dividend_per_share = stock_df.loc[date, 'Dividends']
                    assert isinstance(dividend_per_share, (float, int, np.floating))
                    dividend_per_share = float(dividend_per_share)
                    if dividend_per_share > 0:
                        position = self.positions[symbol]
                        shares_held = position.quantity
                        
                        if shares_held > 0:
                            dividend_value = shares_held * dividend_per_share
                            currency = self._get_stock_currency(symbol)
                            usd_dividend = self._to_usd(dividend_value, currency, date)
                            
                            fund_source = FundSource(
                                source_type='dividend',
                                symbol=symbol,
                                amount_usd=usd_dividend,
                                date=date,
                                transaction_id=len(self.available_funds)
                            )
                            self.available_funds.append(fund_source)

    def create_sankey_diagram(self, title: str = "Portfolio Fund Flow (USD)") -> go.Figure:
        def format_usd(value: float) -> str:
            """Formats a USD value, showing 'K' for thousands if over 100."""
            if abs(value) < 100:
                return f"${value:,.0f}"
            return f"${value / 1000:,.1f}K"
            
        # Calculate net flows for each node for hover display
        node_net_flows = {}
        for flow in self.flow_data:
            source = flow['source']
            target = flow['target']
            value = flow['value']
            
            # Track inflows and outflows for each node
            if source not in node_net_flows:
                node_net_flows[source] = {'inflows': 0, 'outflows': 0}
            if target not in node_net_flows:
                node_net_flows[target] = {'inflows': 0, 'outflows': 0}
            
            node_net_flows[source]['outflows'] += value
            node_net_flows[target]['inflows'] += value
        
        sources = [flow['source'] for flow in self.flow_data]
        targets = [flow['target'] for flow in self.flow_data]
        values = [flow['value'] for flow in self.flow_data]
        customdata = [
            {
                'date': flow['date'].strftime('%Y-%m-%d'),
                'type': flow.get('type', ''),
                'symbol': flow.get('symbol', ''),
                'quantity': flow.get('quantity', ''),
                'price': flow.get('price', ''),
                'from_symbol': flow.get('from_symbol', ''),
                'formatted_value': format_usd(flow['value'])
            }
            for flow in self.flow_data
        ]
        
        # Create node hover data with correct net flows and additional values
        node_customdata = []
        for i, label in enumerate(self.node_labels):
            if i in node_net_flows:
                net_flow = node_net_flows[i]['inflows'] - node_net_flows[i]['outflows']
                # Flip the sign for display
                net_flow_display = format_usd(-net_flow)
                
                # Calculate additional values for stock nodes only
                current_holdings = ""
                if_held_value = ""
                total_sales = ""
                dividends_received = ""
                dividends_if_held = ""
                
                if not self._is_source_node(label):
                    holdings_val, shares_val = self._calculate_current_holdings_value(label)
                    if_held_val, total_shares = self._calculate_if_held_value(label)
                    sales_val = self._calculate_total_sales(label)
                    div_received_val, div_received_shares = self._calculate_dividends_received(label)
                    div_if_held_val, div_if_held_shares = self._calculate_dividends_if_held(label)

                    if holdings_val > 0:
                        current_holdings = f"<br>Current Holdings: {format_usd(holdings_val)} ({int(shares_val)})"
                    
                    if if_held_val > 0:
                        if_held_value = f"<br>If Held Value: {format_usd(if_held_val)} ({total_shares})"
                    
                    if sales_val > 0:
                        total_sales = f"<br>Total Sales: {format_usd(sales_val)}"

                    if div_received_val > 0:
                        dividends_received = f"<br>Dividends Received: {format_usd(div_received_val)}"
                    
                    if div_if_held_val > 0:
                        dividends_if_held = f"<br>Dividends If Held: {format_usd(div_if_held_val)}"
                
                node_customdata.append({
                    'label': label,
                    'net_flow_display': net_flow_display,
                    'current_holdings': current_holdings,
                    'if_held_value': if_held_value,
                    'total_sales': total_sales,
                    'dividends_received': dividends_received,
                    'dividends_if_held': dividends_if_held
                })
            else:
                node_customdata.append({
                    'label': label,
                    'net_flow_display': '$0',
                    'current_holdings': "",
                    'if_held_value': "",
                    'total_sales': "",
                    'dividends_received': "",
                    'dividends_if_held': ""
                })
        
        hovertemplate = (
            'From: %{customdata.from_symbol}<br>'
            'To: %{customdata.symbol}<br>'
            'Date: %{customdata.date}<br>'
            'Type: %{customdata.type}<br>'
            'Quantity: %{customdata.quantity}<br>'
            'Price: %{customdata.price}<br>'
            'Value (USD): %{customdata.formatted_value}<extra></extra>'
        )
        
        node_hovertemplate = (
            'Node: %{customdata.label}<br>'
            'Net Flow: %{customdata.net_flow_display}'
            '%{customdata.current_holdings}'
            '%{customdata.if_held_value}'
            '%{customdata.total_sales}'
            '%{customdata.dividends_received}'
            '%{customdata.dividends_if_held}'
            '<extra></extra>'
        )
        
        # Create Sankey diagram
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=self.node_labels,
                color=self.node_colors,
                customdata=node_customdata,
                hovertemplate=node_hovertemplate
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=['rgba(0,0,0,0.2)'] * len(values),
                customdata=customdata,
                hovertemplate=hovertemplate
            )
        )])
        fig.update_layout(
            title_text=title,
            font_size=10,
            height=800
        )
        return fig

    def save_diagram(self, filename: str = "portfolio_sankey.html"):
        fig = self.create_sankey_diagram()
        fig.write_html(filename)
        print(f"Sankey diagram saved to {filename}")

    def show_diagram(self):
        fig = self.create_sankey_diagram()
        fig.show()

    def _calculate_current_holdings_value(self, symbol: str) -> tuple[float, int]:
        """Calculate the current value of holdings for a given symbol and return (value, shares)."""
        
        if symbol not in self.positions:
            return 0.0, 0
        
        position = self.positions[symbol]
        
        if position.quantity <= 0:
            return 0.0, 0
        
        try:
            # Get the latest price from the stock data
            df = self._get_stock_data(symbol)
            
            if df is not None and not df.empty:
                latest_price = df.iloc[-1]['Close']
                # Get the currency for this symbol
                currency = self._get_stock_currency(symbol)
                # Convert to USD using today's date (or latest available exchange rate)
                today = datetime.now()
                usd_value = self._to_usd(position.quantity * latest_price, currency, today)
                return usd_value, int(position.quantity)
        except Exception as e:
            print(f"Warning: Could not get latest price for {symbol}: {e}")
        
        return 0.0, 0

    def _calculate_if_held_value(self, symbol: str) -> tuple[float, int]:
        """Calculate the hypothetical value if all buy transactions were held and return (value, total_shares)."""
        try:
            # Read transactions to get all buy quantities
            df = self._get_transactions_df()
            
            # Filter for buy transactions for this symbol
            buy_transactions = df[(df['symbol'] == symbol) & (df['transaction'] == 'buy')]
            
            if buy_transactions.empty:
                return 0.0, 0
            
            # Sum all buy quantities
            total_buy_quantity = buy_transactions['quantity'].sum()
            
            # Get the latest price
            stock_df = self._get_stock_data(symbol)
            if stock_df is not None and not stock_df.empty:
                latest_price = stock_df.iloc[-1]['Close']
                # Get the currency for this symbol
                currency = self._get_stock_currency(symbol)
                # Convert to USD using today's date (or latest available exchange rate)
                today = datetime.now()
                if_held_value = self._to_usd(total_buy_quantity * latest_price, currency, today)
                return if_held_value, int(total_buy_quantity)
        except Exception as e:
            print(f"Warning: Could not calculate if-held value for {symbol}: {e}")
        
        return 0.0, 0

    def _calculate_total_sales(self, symbol: str) -> float:
        """Calculate the total value of all sell transactions for a given symbol."""
        try:
            # Read transactions to get all sell values
            df = self._get_transactions_df()
            
            # Filter for sell transactions for this symbol
            sell_transactions = df[(df['symbol'] == symbol) & (df['transaction'] == 'sell')]
            
            if sell_transactions.empty:
                return 0.0
            
            # Get the currency for this symbol
            currency = self._get_stock_currency(symbol)
            
            # Calculate total sales value with currency conversion
            total_sales_usd = 0.0
            for _, transaction in sell_transactions.iterrows():
                quantity = transaction['quantity']
                price = transaction['price']
                date = pd.to_datetime(transaction['date'])
                # Convert each transaction to USD using the transaction date
                transaction_value_usd = self._to_usd(quantity * price, currency, date)
                total_sales_usd += transaction_value_usd
            
            return total_sales_usd
        except Exception as e:
            print(f"Warning: Could not calculate total sales for {symbol}: {e}")
        
        return 0.0

    def _calculate_dividends_received(self, symbol: str) -> tuple[float, int]:
        """Sum of all dividends times the number of shares owned that day, converted to USD."""
        try:
            stock_df = self._get_stock_data(symbol)
            if stock_df is None: return 0.0, 0

            tx_df = self._get_transactions_df()

            tx_df = tx_df[tx_df["symbol"] == symbol].sort_values("date")
            tx_df = tx_df[tx_df["transaction"].isin(["buy", "sell"])]

            if 'Dividends' not in stock_df.columns:
                return 0.0, 0
                
            dividend_dates = stock_df[stock_df['Dividends'] > 0]
            if dividend_dates.empty:
                return 0.0, 0
            
            total_dividends = 0.0
            total_shares_for_dividends = 0
            currency = self._get_stock_currency(symbol)

            for date, stock_row in dividend_dates.iterrows():
                relevant_tx = tx_df[tx_df['date'] <= date]
                shares_held = relevant_tx[relevant_tx['transaction'] == 'buy']['quantity'].sum() - \
                              relevant_tx[relevant_tx['transaction'] == 'sell']['quantity'].sum()

                if shares_held > 0:
                    dividend_per_share = stock_row['Dividends']
                    dividend_value = shares_held * dividend_per_share
                    assert isinstance(date, datetime)
                    total_dividends += self._to_usd(dividend_value, currency, date)
                    total_shares_for_dividends += int(shares_held)
            
            return total_dividends, total_shares_for_dividends
        except Exception as e:
            print(f"Warning: Could not calculate dividends received for {symbol}: {e}")
            return 0.0, 0

    def _calculate_dividends_if_held(self, symbol: str) -> tuple[float, int]:
        """Sum of all dividends times the number of shares that would have been held if never sold, converted to USD."""
        # If the position is still held, there's no "if held" scenario to calculate.
        if symbol in self.positions:
            return 0.0, 0
            
        try:
            stock_df = self._get_stock_data(symbol)
            if stock_df is None: return 0.0, 0

            tx_df = self._get_transactions_df()

            tx_df = tx_df[(tx_df["symbol"] == symbol) & (tx_df["transaction"] == "buy")].sort_values("date")

            if 'Dividends' not in stock_df.columns:
                return 0.0, 0
                
            dividend_dates = stock_df[stock_df['Dividends'] > 0]
            if dividend_dates.empty:
                return 0.0, 0
            
            total_dividends = 0.0
            total_shares_for_dividends = 0
            currency = self._get_stock_currency(symbol)

            for date, stock_row in dividend_dates.iterrows():
                relevant_tx = tx_df[tx_df['date'] <= date]
                shares_held = relevant_tx['quantity'].sum()

                if shares_held > 0:
                    dividend_per_share = stock_row['Dividends']
                    dividend_value = shares_held * dividend_per_share
                    assert isinstance(date, datetime)
                    total_dividends += self._to_usd(dividend_value, currency, date)
                    total_shares_for_dividends += int(shares_held)
            
            return total_dividends, total_shares_for_dividends
        except Exception as e:
            print(f"Warning: Could not calculate dividends if held for {symbol}: {e}")
            return 0.0, 0

    def _is_source_node(self, node_label: str) -> bool:
        """Check if a node is a source node (not a stock symbol)."""
        source_nodes = ["Initial Cash", "RSU Compensation", "ESPP Compensation", "PSU Compensation"]
        return node_label in source_nodes

def main(resources_path: str):
    tracker = PortfolioFlowTracker(resources_path)
    print("Processing transactions...")
    tracker.process_transactions()
    print("Creating Sankey diagram...")
    tracker.save_diagram()
    print("Displaying diagram...")
    tracker.show_diagram()
    print(f"\nSummary:")
    print(f"Total nodes: {len(tracker.node_labels)}")
    print(f"Total flows: {len(tracker.flow_data)}")
    print(f"Current positions: {len(tracker.positions)}")
    for symbol, position in tracker.positions.items():
        print(f"  {symbol}: {position.quantity:.2f} shares ({position.currency})")

def cli_main():
    """CLI entry point for the portfolio visualizer."""
    parser = argparse.ArgumentParser(description="Generate portfolio flow visualization")
    parser.add_argument(
        "--resources-path", 
        type=str, 
        required=True,
        help="Path to the resources directory containing transactions.csv and stock data"
    )
    
    args = parser.parse_args()
    main(args.resources_path)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(cli_main())
