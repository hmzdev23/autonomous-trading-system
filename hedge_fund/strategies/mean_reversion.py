"""
Mean Reversion Strategy — PDF §3.9-3.10: Z-Score Mean Reversion

Entry: Long when z_score < -ENTRY_Z (oversold)
Exit:  Flat when z_score > -EXIT_Z (price reverted toward mean)
Filters: Trend filter (price > SMA-200), Volume filter
Max hold: Force exit after MAX_HOLD_DAYS

From PDF §3.9-3.10, §10.3:
    z_score = (price - rolling_mean(N)) / rolling_std(N)
    Demeaned returns with inverse variance weights (Eq. 314-317)
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class MeanReversionStrategy(Strategy):
    """
    Z-Score mean reversion with trend and volume filters.

    Assigned to: SCHD, SPEM, JPM, GS, BAC, XOM, CVX
    """

    def __init__(self, lookback: int = 20, entry_z: float = 2.0,
                 exit_z: float = 0.5, max_hold: int = 15,
                 stop_loss: float = 0.05, allow_short: bool = False):
        super().__init__(
            name='mean_reversion',
            params={
                'lookback': lookback,
                'entry_z': entry_z,
                'exit_z': exit_z,
                'max_hold': max_hold,
                'stop_loss': stop_loss,
                'allow_short': allow_short,
            }
        )
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.max_hold = max_hold
        self.stop_loss = stop_loss
        self.allow_short = allow_short

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate mean-reversion signals using z-score.
        No lookahead: signal[i] uses only data through day i.
        """
        close = df['Close']

        # Z-score (use precomputed if available, else compute)
        if 'Z_Score_20' in df.columns and self.lookback == 20:
            z = df['Z_Score_20']
        else:
            rolling_mean = close.rolling(self.lookback, min_periods=self.lookback).mean()
            rolling_std = close.rolling(self.lookback, min_periods=self.lookback).std()
            z = (close - rolling_mean) / rolling_std

        # Trend filter: only long when price > SMA-200
        sma_200 = df.get('SMA_200', close.rolling(200, min_periods=200).mean())
        trend_ok = close > sma_200

        # Volume filter: only enter if volume > 20-day avg
        vol_ma = df.get('Volume_MA_20',
                        df['Volume'].rolling(20, min_periods=20).mean()
                        if 'Volume' in df.columns else pd.Series(1, index=df.index))
        volume_ok = df['Volume'] > vol_ma if 'Volume' in df.columns else True

        # Generate signals with max hold and stop-loss
        signal = pd.Series(0, index=df.index, dtype=int)
        in_position = False
        entry_price = 0.0
        hold_days = 0

        for i in range(len(df)):
            if np.isnan(z.iloc[i]):
                signal.iloc[i] = 0
                continue

            if not in_position:
                # Check entry conditions
                if (z.iloc[i] < -self.entry_z and
                    (isinstance(trend_ok, bool) or
                     (not np.isnan(trend_ok.iloc[i]) and trend_ok.iloc[i])) and
                    (isinstance(volume_ok, bool) or
                     (not hasattr(volume_ok, 'iloc') or volume_ok.iloc[i]))):
                    signal.iloc[i] = 1
                    in_position = True
                    entry_price = close.iloc[i]
                    hold_days = 1
                else:
                    signal.iloc[i] = 0
            else:
                hold_days += 1

                # Check exit conditions (priority order)
                # 1. Stop-loss
                if close.iloc[i] < entry_price * (1 - self.stop_loss):
                    signal.iloc[i] = 0
                    in_position = False
                # 2. Max hold exceeded
                elif hold_days > self.max_hold:
                    signal.iloc[i] = 0
                    in_position = False
                # 3. Z-score reverted (exit zone)
                elif z.iloc[i] > -self.exit_z:
                    signal.iloc[i] = 0
                    in_position = False
                else:
                    signal.iloc[i] = 1

        return signal
