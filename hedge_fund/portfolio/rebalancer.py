"""
Monthly portfolio rebalancer.
Computes target vs current allocations and generates trades.
"""

import pandas as pd
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)


class Rebalancer:
    """
    Executes monthly rebalance trades.
    Computes target weights → diffs vs current holdings →
    generates BUY/SELL orders.
    """

    def compute_trades(self, current_positions: dict,
                       target_weights: dict,
                       portfolio_value: float,
                       prices: dict) -> list[dict]:
        """
        Compute trades needed to reach target allocation.

        Args:
            current_positions: {ticker: shares}
            target_weights: {ticker: weight} (0-1)
            portfolio_value: total portfolio value
            prices: {ticker: current_price}

        Returns:
            List of {ticker, action, shares, estimated_value}
        """
        trades = []

        # All tickers we need to consider
        all_tickers = set(list(current_positions.keys()) +
                          list(target_weights.keys()))

        for ticker in sorted(all_tickers):
            current_shares = current_positions.get(ticker, 0)
            current_price = prices.get(ticker, 0)

            if current_price <= 0:
                continue

            current_value = current_shares * current_price
            target_value = target_weights.get(ticker, 0) * portfolio_value
            diff_value = target_value - current_value

            # Only trade if difference is meaningful (> 0.5% of portfolio)
            if abs(diff_value) < portfolio_value * 0.005:
                continue

            diff_shares = diff_value / current_price

            if diff_shares > 0:
                trades.append({
                    'ticker': ticker,
                    'action': 'BUY',
                    'shares': round(diff_shares, 4),
                    'estimated_value': abs(diff_value),
                })
            elif diff_shares < 0:
                trades.append({
                    'ticker': ticker,
                    'action': 'SELL',
                    'shares': round(abs(diff_shares), 4),
                    'estimated_value': abs(diff_value),
                })

        return trades
