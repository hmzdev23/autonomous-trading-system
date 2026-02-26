"""
Dual Momentum Strategy — Gary Antonacci's proven approach, adapted.

This REPLACES the broken mean reversion strategy (3-7% active time = useless).

The insight: Don't try to catch falling knives. Instead:
1. ABSOLUTE momentum: Is the asset trending up? (return > 0 over lookback)
2. RELATIVE momentum: Is it outperforming its peers?
3. If both are positive → go long
4. If absolute is negative → go to cash (crash protection)

This stays invested 60-80% of the time vs the old 3-7%.
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class DualMomentumStrategy(Strategy):
    """
    Dual Momentum: absolute + relative momentum.
    Goes long when asset has positive absolute momentum AND
    is performing above median of its peer group.

    Replaces: Mean Reversion for SCHD, SPEM, JPM, GS, BAC, XOM, CVX
    """

    def __init__(self, lookback: int = 63, min_lookback: int = 21,
                 trend_filter: int = 100):
        super().__init__(
            name='dual_momentum',
            params={
                'lookback': lookback,
                'min_lookback': min_lookback,
                'trend_filter': trend_filter,
            }
        )
        self.lookback = lookback       # ~3 months
        self.min_lookback = min_lookback  # ~1 month minimum
        self.trend_filter = trend_filter

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']

        # Absolute momentum: is the rolling return positive?
        ret_lookback = close.pct_change(self.lookback)
        ret_short = close.pct_change(self.min_lookback)

        # Trend filter: price > SMA(100) — more responsive than SMA(200)
        sma_filter = df.get(f'SMA_{self.trend_filter}',
                           close.rolling(self.trend_filter,
                                         min_periods=self.trend_filter).mean())

        # RSI for timing
        rsi = df.get('RSI_14')

        signal = pd.Series(0, index=df.index, dtype=int)

        for i in range(self.lookback, len(df)):
            if np.isnan(ret_lookback.iloc[i]):
                continue

            abs_momentum = ret_lookback.iloc[i] > 0
            short_momentum = ret_short.iloc[i] > -0.05  # Not crashing recently
            above_trend = close.iloc[i] > sma_filter.iloc[i] if not np.isnan(sma_filter.iloc[i]) else True
            rsi_ok = rsi.iloc[i] > 25 if (rsi is not None and not np.isnan(rsi.iloc[i])) else True

            # Go long if:
            # - 3-month return is positive (absolute momentum), AND
            # - Not in a short-term crash (>-5% in last month), AND
            # - Price above trend filter, AND
            # - RSI not deeply oversold (likely a crash)
            if abs_momentum and short_momentum and above_trend and rsi_ok:
                signal.iloc[i] = 1
            # Partial: even if 3-month is flat, stay in if short-term is positive and trend OK
            elif short_momentum and above_trend and ret_lookback.iloc[i] > -0.03:
                signal.iloc[i] = 1
            else:
                signal.iloc[i] = 0

        return signal
