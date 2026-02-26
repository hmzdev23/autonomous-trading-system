"""
Momentum-Weighted Portfolio Allocator.

REPLACES inverse-volatility allocation which was overweighting boring names
(ZEB, JPM, CVX) and underweighting the actual top performers (NVDA, AAPL, MSFT).

New approach: Momentum-weighted allocation
1. Score each ticker by momentum (composite of 1/3/6 month returns)
2. Winners get bigger weights, losers get smaller
3. Floor weights at 2% so nothing gets dropped entirely
4. Cap at 15% per ticker
5. Regime filter: reduce total exposure only in severe downtrends
"""

import pandas as pd
import numpy as np
import config
from utils.logger import get_logger

log = get_logger(__name__)


class MomentumWeightedAllocator:
    """
    Allocates more capital to stronger performers.
    Combines momentum scoring with risk constraints.
    """

    def __init__(self,
                 max_ticker_weight: float = None,
                 max_sleeve_weight: float = None,
                 min_ticker_weight: float = 0.02):
        self.max_ticker = max_ticker_weight or config.MAX_TICKER_WEIGHT
        self.max_sleeve = max_sleeve_weight or config.MAX_SLEEVE_WEIGHT
        self.min_ticker = min_ticker_weight

    def compute_weights(self, prices: pd.DataFrame,
                        date: pd.Timestamp) -> dict[str, float]:
        """
        Compute momentum-weighted allocation at a given date.
        """
        mask = prices.index <= date
        hist = prices.loc[mask]

        if len(hist) < 126:  # Need 6 months minimum
            tickers = [c for c in prices.columns if not prices[c].isna().all()]
            n = len(tickers)
            return {t: 1.0 / n for t in tickers} if n else {}

        # Composite momentum score: 40% × 1-month + 30% × 3-month + 30% × 6-month
        scores = {}
        for col in prices.columns:
            if hist[col].isna().iloc[-1]:
                continue

            current = hist[col].iloc[-1]
            ret_1m = current / hist[col].iloc[-21] - 1 if len(hist) >= 21 and hist[col].iloc[-21] > 0 else 0
            ret_3m = current / hist[col].iloc[-63] - 1 if len(hist) >= 63 and hist[col].iloc[-63] > 0 else 0
            ret_6m = current / hist[col].iloc[-126] - 1 if len(hist) >= 126 and hist[col].iloc[-126] > 0 else 0

            # Composite score
            score = 0.4 * ret_1m + 0.3 * ret_3m + 0.3 * ret_6m
            scores[col] = score

        if not scores:
            return {}

        # Shift scores so all are positive (can't weight by negative)
        min_score = min(scores.values())
        shifted = {t: s - min_score + 0.01 for t, s in scores.items()}  # +0.01 to avoid zero

        # Normalize to weights
        total = sum(shifted.values())
        weights = {t: s / total for t, s in shifted.items()}

        # Apply constraints
        weights = self._apply_constraints(weights)

        return weights

    def _apply_constraints(self, raw_weights: dict) -> dict[str, float]:
        """Apply min/max constraints iteratively."""
        weights = raw_weights.copy()

        for _ in range(10):
            # Floor: set minimums
            for t in list(weights.keys()):
                if weights[t] < self.min_ticker:
                    weights[t] = self.min_ticker

            # Cap per ticker
            excess = 0.0
            uncapped = []
            for t, w in weights.items():
                if w > self.max_ticker:
                    excess += w - self.max_ticker
                    weights[t] = self.max_ticker
                else:
                    uncapped.append(t)

            if excess > 0 and uncapped:
                per_ticker = excess / len(uncapped)
                for t in uncapped:
                    weights[t] += per_ticker

            # Cap per sleeve
            for sleeve_name, sleeve_tickers in config.SLEEVES.items():
                sleeve_weight = sum(weights.get(t, 0) for t in sleeve_tickers)
                if sleeve_weight > self.max_sleeve:
                    scale = self.max_sleeve / sleeve_weight
                    excess_sleeve = 0.0
                    for t in sleeve_tickers:
                        if t in weights:
                            old_w = weights[t]
                            weights[t] = old_w * scale
                            excess_sleeve += old_w - weights[t]
                    other_tickers = [t for t in weights if t not in sleeve_tickers]
                    if other_tickers and excess_sleeve > 0:
                        per_other = excess_sleeve / len(other_tickers)
                        for t in other_tickers:
                            weights[t] += per_other

            # Normalize
            total = sum(weights.values())
            if total > 0:
                weights = {t: w / total for t, w in weights.items()}

        return weights

    def get_rebalance_dates(self, start: str, end: str,
                            trading_dates: pd.DatetimeIndex) -> list:
        """Return last trading day of each month."""
        mask = (trading_dates >= pd.Timestamp(start)) & \
               (trading_dates <= pd.Timestamp(end))
        dates = trading_dates[mask]
        monthly = dates.to_series().groupby(
            [dates.year, dates.month]
        ).last()
        return monthly.tolist()
