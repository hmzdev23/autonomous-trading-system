"""
Leveraged Momentum Strategy — for 3x ETFs (TQQQ, SOXL, UPRO, SPXL, TECL).

Aggressive intraday/swing approach designed for leveraged instruments.
Key differences from standard momentum:
  - MUCH faster signals: EMA(5/13) instead of EMA(12/26)
  - Tighter trailing stop: 5% instead of 12% (3x leverage = 3x risk)
  - Max hold: 5 days (avoid leveraged decay / volatility drag)
  - RSI for timing: don't enter overbought, don't exit oversold reversal
  - Volume confirmation: only enter on above-average volume

Derived from PDF §3.12 (Two Moving Averages) with parameters compressed
for leveraged instruments per §4.6 risk-adjusted weighting principles.
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class LeveragedMomentumStrategy(Strategy):
    """
    Fast EMA crossover for 3x leveraged ETFs.

    Entry:   EMA(5) > EMA(13) + RSI(14) > 40 + volume above 20-day avg
    Exit:    EMA bearish crossover OR 5% trailing stop OR RSI < 25 OR max hold reached
    """

    def __init__(self, ema_fast: int = 5, ema_slow: int = 13,
                 trailing_stop: float = 0.05, max_hold_days: int = 5,
                 rsi_entry_floor: int = 40, rsi_exit_floor: int = 25):
        super().__init__(
            name='leveraged_momentum',
            params={
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'trailing_stop': trailing_stop,
                'max_hold_days': max_hold_days,
                'rsi_entry_floor': rsi_entry_floor,
                'rsi_exit_floor': rsi_exit_floor,
            }
        )
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.trailing_stop = trailing_stop
        self.max_hold_days = max_hold_days
        self.rsi_entry_floor = rsi_entry_floor
        self.rsi_exit_floor = rsi_exit_floor

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']

        # Fast EMAs for leveraged instruments
        ema_f = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema_s = close.ewm(span=self.ema_slow, adjust=False).mean()

        # MACD histogram (fast version)
        macd_line = ema_f - ema_s
        signal_line = macd_line.ewm(span=5, adjust=False).mean()
        macd_hist = macd_line - signal_line

        # RSI(14)
        rsi = df.get('RSI_14')
        if rsi is None:
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
            avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
            rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        # Volume filter
        volume = df.get('Volume')
        vol_ma = volume.rolling(20, min_periods=10).mean() if volume is not None else None

        # SMA(20) as short-term trend filter
        sma_20 = close.rolling(20, min_periods=20).mean()

        signal = pd.Series(0, index=df.index, dtype=int)
        in_position = False
        peak_price = 0.0
        hold_days = 0

        warmup = max(self.ema_slow, 20)

        for i in range(warmup, len(df)):
            if np.isnan(ema_f.iloc[i]) or np.isnan(ema_s.iloc[i]):
                continue

            ema_bullish = ema_f.iloc[i] > ema_s.iloc[i]
            macd_positive = macd_hist.iloc[i] > 0 if not np.isnan(macd_hist.iloc[i]) else False
            rsi_val = rsi.iloc[i] if not np.isnan(rsi.iloc[i]) else 50
            above_sma20 = close.iloc[i] > sma_20.iloc[i] if not np.isnan(sma_20.iloc[i]) else True

            # Volume confirmation
            vol_ok = True
            if vol_ma is not None and volume is not None:
                if not np.isnan(vol_ma.iloc[i]) and vol_ma.iloc[i] > 0:
                    vol_ok = volume.iloc[i] > vol_ma.iloc[i] * 0.8  # 80% of avg

            if not in_position:
                # ENTRY: EMA bullish + above SMA20 + RSI not overbought/oversold
                # + MACD confirming + volume OK
                if (ema_bullish and above_sma20 and
                        rsi_val > self.rsi_entry_floor and rsi_val < 80 and
                        macd_positive and vol_ok):
                    signal.iloc[i] = 1
                    in_position = True
                    peak_price = close.iloc[i]
                    hold_days = 0
                # Relaxed entry: strong momentum even without all confirmations
                elif ema_bullish and rsi_val > 50 and above_sma20:
                    signal.iloc[i] = 1
                    in_position = True
                    peak_price = close.iloc[i]
                    hold_days = 0
            else:
                hold_days += 1

                # Update trailing stop
                if close.iloc[i] > peak_price:
                    peak_price = close.iloc[i]

                drawdown = (peak_price - close.iloc[i]) / peak_price

                # EXIT conditions (any triggers exit):
                exit_signal = False

                # 1. Trailing stop hit
                if drawdown > self.trailing_stop:
                    exit_signal = True

                # 2. Max hold reached (avoid leveraged decay)
                if hold_days >= self.max_hold_days:
                    exit_signal = True

                # 3. Full bearish confirmation
                if not ema_bullish and not macd_positive and rsi_val < self.rsi_exit_floor:
                    exit_signal = True

                # 4. EMA bearish + significant drawdown
                if not ema_bullish and drawdown > self.trailing_stop * 0.5:
                    exit_signal = True

                if exit_signal:
                    signal.iloc[i] = 0
                    in_position = False
                    peak_price = 0.0
                    hold_days = 0
                else:
                    signal.iloc[i] = 1

        return signal
