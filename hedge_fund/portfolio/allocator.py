"""
Inverse Volatility Portfolio Allocator.

Risk-weighted allocation using inverse volatility weighting.
Formula: weight_i = (1/vol_i) / sum(1/vol_j)
With constraints: max 15% per ticker, max 35% per sleeve, min 1% per ticker.
"""

import pandas as pd
import numpy as np
import config
from utils.logger import get_logger

log = get_logger(__name__)


class InverseVolAllocator:
    """
    Risk-weighted portfolio allocation using inverse volatility.

    From PDF §4.6 (Eq. 372-373): vol-adjusted weighting.
    """

    def __init__(self,
                 vol_lookback: int = None,
                 max_ticker_weight: float = None,
                 max_sleeve_weight: float = None,
                 min_ticker_weight: float = None):
        self.vol_lookback = vol_lookback or config.VOL_LOOKBACK_DAYS
        self.max_ticker = max_ticker_weight or config.MAX_TICKER_WEIGHT
        self.max_sleeve = max_sleeve_weight or config.MAX_SLEEVE_WEIGHT
        self.min_ticker = min_ticker_weight or config.MIN_TICKER_WEIGHT

    def compute_weights(self, prices: pd.DataFrame,
                        date: pd.Timestamp) -> dict[str, float]:
        """
        Compute inverse-vol weights for all tickers at a given date.
        prices: DataFrame with ticker columns and datetime index.
        Returns: {ticker: weight} dict that sums to 1.0
        """
        # Get lookback window of returns ending at 'date'
        mask = prices.index <= date
        lookback_prices = prices.loc[mask].tail(self.vol_lookback + 1)

        if len(lookback_prices) < self.vol_lookback:
            # Not enough data — equal weight
            tickers = [c for c in prices.columns if not prices[c].isna().all()]
            n = len(tickers)
            return {t: 1.0 / n for t in tickers} if n else {}

        returns = lookback_prices.pct_change(fill_method=None).dropna()

        # Annualized volatility
        vols = returns.std() * np.sqrt(252)
        vols = vols.replace(0, np.nan).dropna()

        if len(vols) == 0:
            return {}

        # Inverse volatility weights
        inv_vol = 1.0 / vols
        raw_weights = inv_vol / inv_vol.sum()

        # Apply constraints
        weights = self.apply_constraints(raw_weights.to_dict())

        return weights

    def apply_constraints(self, raw_weights: dict) -> dict[str, float]:
        """
        Apply allocation constraints iteratively:
        1. Drop tickers below min weight
        2. Cap tickers at max weight, redistribute
        3. Cap sleeves at max weight, redistribute
        4. Round to nearest 0.5%
        """
        weights = raw_weights.copy()

        # Iteration to converge
        for _ in range(10):
            # 1. Drop below minimum
            to_drop = [t for t, w in weights.items() if w < self.min_ticker]
            for t in to_drop:
                del weights[t]

            if not weights:
                break

            # Renormalize
            total = sum(weights.values())
            if total > 0:
                weights = {t: w / total for t, w in weights.items()}

            # 2. Cap per ticker
            excess = 0.0
            uncapped = []
            for t, w in weights.items():
                if w > self.max_ticker:
                    excess += w - self.max_ticker
                    weights[t] = self.max_ticker
                else:
                    uncapped.append(t)

            # Redistribute excess to uncapped tickers
            if excess > 0 and uncapped:
                per_ticker = excess / len(uncapped)
                for t in uncapped:
                    weights[t] += per_ticker

            # 3. Cap per sleeve
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

                    # Redistribute to other sleeves
                    other_tickers = [t for t in weights
                                     if t not in sleeve_tickers]
                    if other_tickers and excess_sleeve > 0:
                        per_other = excess_sleeve / len(other_tickers)
                        for t in other_tickers:
                            weights[t] += per_other

            # Renormalize to sum to 1.0
            total = sum(weights.values())
            if total > 0:
                weights = {t: w / total for t, w in weights.items()}

        # 4. Round to nearest 0.5%
        weights = {t: round(w * 200) / 200 for t, w in weights.items()}

        # Final renormalize
        total = sum(weights.values())
        if total > 0:
            weights = {t: w / total for t, w in weights.items()}

        return weights

    def get_rebalance_dates(self, start: str, end: str,
                            trading_dates: pd.DatetimeIndex) -> list:
        """
        Return the last trading day of each month in the range.
        """
        mask = (trading_dates >= pd.Timestamp(start)) & \
               (trading_dates <= pd.Timestamp(end))
        dates = trading_dates[mask]

        # Group by year-month, take last date
        monthly = dates.to_series().groupby(
            [dates.year, dates.month]
        ).last()

        return monthly.tolist()

    def compute_weight_history(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        Compute weights at each rebalance date.
        Returns DataFrame: index=date, columns=tickers, values=weights.
        """
        rebal_dates = self.get_rebalance_dates(
            str(prices.index.min().date()),
            str(prices.index.max().date()),
            prices.index,
        )

        records = []
        for date in rebal_dates:
            weights = self.compute_weights(prices, date)
            weights['date'] = date
            records.append(weights)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records).set_index('date')
        df = df.fillna(0)
        return df
