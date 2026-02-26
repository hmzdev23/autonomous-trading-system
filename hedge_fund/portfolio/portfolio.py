"""
Portfolio state tracking — positions, cash, P&L.
"""

import pandas as pd
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)


class Portfolio:
    """
    Tracks portfolio state during backtest or live trading.
    """

    def __init__(self, initial_capital: float = 10_000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {ticker: {'shares': float, 'avg_price': float}}
        self.trade_log = []  # List of trade dicts
        self.equity_history = []  # (date, equity_value)

    @property
    def total_value(self) -> float:
        """Placeholder — use update_equity with current prices."""
        return self.cash + sum(
            p['shares'] * p['last_price']
            for p in self.positions.values()
            if 'last_price' in p
        )

    def update_equity(self, date, prices: dict):
        """Record equity value at end of day."""
        equity = self.cash
        for ticker, pos in self.positions.items():
            if ticker in prices and not np.isnan(prices[ticker]):
                pos['last_price'] = prices[ticker]
                equity += pos['shares'] * prices[ticker]
        self.equity_history.append((date, equity))

    def execute_trade(self, ticker: str, shares: float, price: float,
                      date, side: str, slippage: float = 0.001,
                      commission: float = 1.0):
        """
        Execute a trade (buy or sell).
        """
        execution_price = price * (1 + slippage) if side == 'BUY' \
            else price * (1 - slippage)

        cost = abs(shares) * execution_price + commission

        if side == 'BUY':
            self.cash -= cost
            if ticker in self.positions:
                old = self.positions[ticker]
                total_shares = old['shares'] + shares
                total_cost = old['shares'] * old['avg_price'] + shares * execution_price
                self.positions[ticker] = {
                    'shares': total_shares,
                    'avg_price': total_cost / total_shares if total_shares else 0,
                    'last_price': price,
                }
            else:
                self.positions[ticker] = {
                    'shares': shares,
                    'avg_price': execution_price,
                    'last_price': price,
                }
        else:  # SELL
            self.cash += abs(shares) * execution_price - commission
            if ticker in self.positions:
                self.positions[ticker]['shares'] -= abs(shares)
                if self.positions[ticker]['shares'] <= 0.001:
                    del self.positions[ticker]

        self.trade_log.append({
            'date': date,
            'ticker': ticker,
            'side': side,
            'shares': abs(shares),
            'price': execution_price,
            'commission': commission,
            'cash_after': self.cash,
        })

    def get_equity_series(self) -> pd.Series:
        """Return equity curve as a pandas Series."""
        if not self.equity_history:
            return pd.Series(dtype=float)
        dates, values = zip(*self.equity_history)
        return pd.Series(values, index=pd.DatetimeIndex(dates), name='Equity')

    def get_trade_df(self) -> pd.DataFrame:
        """Return trade log as DataFrame."""
        if not self.trade_log:
            return pd.DataFrame()
        return pd.DataFrame(self.trade_log)
