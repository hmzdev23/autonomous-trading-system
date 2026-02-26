"""
Sector Momentum Rotation Strategy — PDF §4.1.1

Rank sector ETFs by cumulative return over lookback period.
Buy top-ranked ETFs only if price > MA filter.
If market index < MA, move to cash.

From PDF Eq. 362-363:
    R_cum_i = cumulative return of ETF i over T months
    Rule = Buy top ETFs if P > MA(T')
           Cash if P ≤ MA(T')
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class SectorMomentumStrategy(Strategy):
    """
    Sector momentum rotation with MA trend filter.

    Assigned to: FTXL, ZEB, XLE
    """

    def __init__(self, lookback: int = 126, ma_filter: int = 200,
                 top_fraction: float = 0.5):
        super().__init__(
            name='sector_momentum',
            params={
                'lookback': lookback,
                'ma_filter': ma_filter,
                'top_fraction': top_fraction,
            }
        )
        self.lookback = lookback
        self.ma_filter = ma_filter
        self.top_fraction = top_fraction

    def generate_signals(self, df: pd.DataFrame,
                         all_sector_data: dict = None) -> pd.Series:
        """
        Generate sector momentum signals for a single ETF.

        For the simplified case (single-ETF evaluation):
        - Go long if cumulative return > 0 AND price > MA(200)
        - Go flat otherwise

        For full cross-sectional ranking (if all_sector_data provided):
        - Rank all sector ETFs by cumulative return
        - Only invest in top_fraction of them
        """
        close = df['Close']

        # MA filter
        sma_key = f'SMA_{self.ma_filter}'
        if sma_key in df.columns:
            sma_long = df[sma_key]
        else:
            sma_long = close.rolling(self.ma_filter,
                                     min_periods=self.ma_filter).mean()

        # Cumulative return over lookback period
        cum_ret = close.pct_change(self.lookback)

        # Signal: long if positive momentum AND price above long-term MA
        signal = pd.Series(0, index=df.index, dtype=int)

        for i in range(len(df)):
            if (i >= self.lookback and
                not np.isnan(cum_ret.iloc[i]) and
                not np.isnan(sma_long.iloc[i])):

                if cum_ret.iloc[i] > 0 and close.iloc[i] > sma_long.iloc[i]:
                    signal.iloc[i] = 1
                else:
                    signal.iloc[i] = 0

        return signal
