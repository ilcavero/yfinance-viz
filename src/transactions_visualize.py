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
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

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
    def __init__(self, resources_path: str = "src/resources"):
        self.resources_path = resources_path
        self.positions: Dict[str, Position] = {}
        self.available_funds: List[FundSource] = []
        self.flow_data: List[Dict] = []
        self.node_labels: List[str] = []
        self.node_colors: List[str] = []
        self.currency_cache: Dict[str, str] = {}
        self.exchange_rates: Dict[str, float] = {}
        self.node_map: Dict[str, int] = {}  # symbol -> node index
        self._load_exchange_rates()
        self.node_labels = ["Initial Cash"]
        self.node_colors = ["#1f77b4"]
        self.node_map["Initial Cash"] = 0

    def _load_exchange_rates(self):
        try:
            eurusd_file = os.path.join(self.resources_path, "EURUSD=X.csv")
            eurusd_df = pd.read_csv(eurusd_file)
            eurusd_df['Date'] = pd.to_datetime(eurusd_df['Date'], utc=True)
            for _, row in eurusd_df.iterrows():
                date_str = row['Date'].strftime('%Y-%m-%d')
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
            stock_file = os.path.join(self.resources_path, f"{symbol}.csv")
            if os.path.exists(stock_file):
                df = pd.read_csv(stock_file)
                if 'Currency' in df.columns and len(df) > 0:
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

    def process_transactions(self, transactions_file: str = "src/resources/transactions.csv"):
        """Process all transactions and build the flow data."""
        df = pd.read_csv(transactions_file)
        
        # Sort by date, then by transaction type (sell=0, buy=1), then by row order
        df['transaction_type'] = df['transaction'].map({'sell': 0, 'buy': 1})
        df = df.sort_values(['date', 'transaction_type']).reset_index(drop=True)
        
        for idx, transaction in df.iterrows():
            transaction_type = transaction['transaction']
            symbol = transaction['symbol']
            source = str(transaction.get('source', '')).upper()
            
            # Add nodes for all symbols first
            self._add_node(symbol)
            
            if transaction_type == 'sell':
                usd_value = self._process_sell_transaction(transaction)
            elif transaction_type == 'buy' and source in ['RSU', 'ESPP', 'PSU']:
                # Employment compensation transactions should NOT allocate funds from sells
                # They are self-funded from their compensation sources
                usd_value = self._process_buy_transaction(transaction)
                
                # Create flow data for employment compensation only
                source_label = f"{source} Compensation"
                if source_label not in self.node_map:
                    self.node_labels.append(source_label)
                    self.node_colors.append("#2ca02c")
                    self.node_map[source_label] = len(self.node_labels) - 1
                source_idx = self.node_map[source_label]
                target_idx = self.node_map[symbol]
                self.flow_data.append({
                    'source': source_idx,
                    'target': target_idx,
                    'value': usd_value,
                    'date': transaction['date'],
                    'type': source,
                    'symbol': symbol,
                    'quantity': transaction['quantity'],
                    'price': transaction['price'],
                    'from_symbol': source_label,
                })
            elif transaction_type == 'buy':
                usd_value = self._process_buy_transaction(transaction)
                allocated = self._allocate_funds(usd_value, symbol, pd.to_datetime(transaction['date']))
                
                # Aggregate allocations by source node
                aggregated_allocations = {}
                for source_symbol, amount in allocated:
                    if source_symbol not in aggregated_allocations:
                        aggregated_allocations[source_symbol] = 0
                    aggregated_allocations[source_symbol] += amount
                
                # Create flow data for the aggregated allocations
                for source_symbol, total_amount in aggregated_allocations.items():
                    source_idx = self.node_map[source_symbol]
                    target_idx = self.node_map[symbol]
                    self.flow_data.append({
                        'source': source_idx,
                        'target': target_idx,
                        'value': total_amount,
                        'date': transaction['date'],
                        'type': 'Funds',
                        'symbol': symbol,
                        'quantity': transaction['quantity'],
                        'price': transaction['price'],
                        'from_symbol': source_symbol,
                    })
        


    def create_sankey_diagram(self, title: str = "Portfolio Fund Flow (USD)") -> go.Figure:
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
                'date': flow['date'],
                'type': flow.get('type', ''),
                'symbol': flow.get('symbol', ''),
                'quantity': flow.get('quantity', ''),
                'price': flow.get('price', ''),
                'from_symbol': flow.get('from_symbol', ''),
            }
            for flow in self.flow_data
        ]
        
        # Create node hover data with correct net flows and additional values
        node_customdata = []
        for i, label in enumerate(self.node_labels):
            if i in node_net_flows:
                net_flow = node_net_flows[i]['inflows'] - node_net_flows[i]['outflows']
                # Flip the sign and convert to thousands
                net_flow_flipped = -net_flow / 1000
                
                # Calculate additional values for stock nodes only
                current_holdings = ""
                if_held_value = ""
                total_sales = ""
                
                if not self._is_source_node(label):
                    holdings_val, shares_val = self._calculate_current_holdings_value(label)
                    if_held_val, total_shares = self._calculate_if_held_value(label)
                    sales_val = self._calculate_total_sales(label)
                    
                    if holdings_val > 0:
                        current_holdings = f"<br>Current Holdings: ${holdings_val / 1000:.1f}K ({int(shares_val)})"
                    
                    if if_held_val > 0:
                        if_held_value = f"<br>If Held Value: ${if_held_val / 1000:.1f}K ({total_shares})"
                    
                    if sales_val > 0:
                        total_sales = f"<br>Total Sales: ${sales_val / 1000:.1f}K"
                
                node_customdata.append({
                    'label': label,
                    'net_flow_flipped': net_flow_flipped,
                    'current_holdings': current_holdings,
                    'if_held_value': if_held_value,
                    'total_sales': total_sales
                })
            else:
                node_customdata.append({
                    'label': label,
                    'net_flow_flipped': 0,
                    'current_holdings': "",
                    'if_held_value': "",
                    'total_sales': ""
                })
        
        hovertemplate = (
            'From: %{customdata.from_symbol}<br>'
            'To: %{customdata.symbol}<br>'
            'Date: %{customdata.date}<br>'
            'Type: %{customdata.type}<br>'
            'Quantity: %{customdata.quantity}<br>'
            'Price: %{customdata.price}<br>'
            'Value (USD): %{value}<extra></extra>'
        )
        
        node_hovertemplate = (
            'Node: %{customdata.label}<br>'
            'Net Flow: $%{customdata.net_flow_flipped:.1f}K'
            '%{customdata.current_holdings}'
            '%{customdata.if_held_value}'
            '%{customdata.total_sales}'
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
            stock_file = os.path.join(self.resources_path, f"{symbol}.csv")
            
            if os.path.exists(stock_file):
                df = pd.read_csv(stock_file)
                if not df.empty:
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
            transactions_file = os.path.join(self.resources_path, "transactions.csv")
            df = pd.read_csv(transactions_file)
            
            # Filter for buy transactions for this symbol
            buy_transactions = df[(df['symbol'] == symbol) & (df['transaction'] == 'buy')]
            
            if buy_transactions.empty:
                return 0.0, 0
            
            # Sum all buy quantities
            total_buy_quantity = buy_transactions['quantity'].sum()
            
            # Get the latest price
            stock_file = os.path.join(self.resources_path, f"{symbol}.csv")
            if os.path.exists(stock_file):
                stock_df = pd.read_csv(stock_file)
                if not stock_df.empty:
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
            transactions_file = os.path.join(self.resources_path, "transactions.csv")
            df = pd.read_csv(transactions_file)
            
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

    def _is_source_node(self, node_label: str) -> bool:
        """Check if a node is a source node (not a stock symbol)."""
        source_nodes = ["Initial Cash", "RSU Compensation", "ESPP Compensation", "PSU Compensation"]
        return node_label in source_nodes

def main():
    tracker = PortfolioFlowTracker()
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

if __name__ == "__main__":
    main()
