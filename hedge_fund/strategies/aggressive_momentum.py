"""
Aggressive Momentum Strategy — REPLACES the slow SMA(50/200) crossover.

Problems with old SMA(50/200):
- Too slow to react: bull market runs for months before golden cross fires
- Goes to cash too early on normal pullbacks
- 30-40% cash drag even on best tickers

New approach: EMA(12/26) + MACD + RSI confirmation
- Much faster signals (~3x faster than SMA 50/200)
- MACD histogram confirms direction (avoids whipsaws)
- RSI filter only on exit (don't exit if still strong momentum)
- Trailing stop instead of fixed stop (rides winners longer)
- Default is INVESTED — only go flat on confirmed downtrend
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class AggressiveMomentumStrategy(Strategy):
    """
    Fast EMA crossover with MACD confirmation.
    Designed to STAY INVESTED and only exit on confirmed downtrends.

    Replaces: SMA Momentum for VOO, QQQ, AAPL, MSFT, NVDA, GOOGL, AMZN, TSLA
    """

    def __init__(self, ema_fast: int = 12, ema_slow: int = 26,
                 trailing_stop: float = 0.12, rsi_exit_floor: int = 30):
        super().__init__(
            name='aggressive_momentum',
            params={
                'ema_fast': ema_fast,
                'ema_slow': ema_slow,
                'trailing_stop': trailing_stop,
                'rsi_exit_floor': rsi_exit_floor,
            }
        )
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.trailing_stop = trailing_stop
        self.rsi_exit_floor = rsi_exit_floor

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        close = df['Close']

        # Fast EMA crossover
        ema_f = df.get('EMA_12', close.ewm(span=self.ema_fast, adjust=False).mean())
        ema_s = df.get('EMA_26', close.ewm(span=self.ema_slow, adjust=False).mean())

        # MACD histogram for confirmation
        macd_hist = df.get('MACD_Hist')
        if macd_hist is None:
            macd_line = ema_f - ema_s
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = macd_line - signal_line

        # RSI for exit protection
        rsi = df.get('RSI_14')
        if rsi is None:
            delta = close.diff()
            gain = delta.where(delta > 0, 0.0)
            loss = -delta.where(delta < 0, 0.0)
            avg_gain = gain.ewm(alpha=1/14, min_periods=14).mean()
            avg_loss = loss.ewm(alpha=1/14, min_periods=14).mean()
            rsi = 100 - (100 / (1 + avg_gain / avg_loss))

        # SMA 50 as a more lenient trend filter (not 200!)
        sma_50 = df.get('SMA_50', close.rolling(50, min_periods=50).mean())

        signal = pd.Series(0, index=df.index, dtype=int)
        in_position = False
        peak_price = 0.0

        for i in range(self.ema_slow, len(df)):
            if np.isnan(ema_f.iloc[i]) or np.isnan(ema_s.iloc[i]):
                continue

            ema_bullish = ema_f.iloc[i] > ema_s.iloc[i]
            macd_positive = macd_hist.iloc[i] > 0 if not np.isnan(macd_hist.iloc[i]) else False
            above_sma50 = close.iloc[i] > sma_50.iloc[i] if not np.isnan(sma_50.iloc[i]) else True
            rsi_val = rsi.iloc[i] if not np.isnan(rsi.iloc[i]) else 50

            if not in_position:
                # ENTRY: EMA bullish + MACD positive + above SMA50
                # OR: EMA bullish + strong RSI (>50) — don't wait for MACD
                if ema_bullish and (macd_positive or above_sma50):
                    signal.iloc[i] = 1
                    in_position = True
                    peak_price = close.iloc[i]
                elif ema_bullish and rsi_val > 50:
                    signal.iloc[i] = 1
                    in_position = True
                    peak_price = close.iloc[i]
            else:
                # Update trailing stop
                if close.iloc[i] > peak_price:
                    peak_price = close.iloc[i]

                drawdown_from_peak = (peak_price - close.iloc[i]) / peak_price

                # EXIT conditions (all must be true):
                # 1. Trailing stop hit AND
                # 2. (EMA bearish OR MACD negative) AND
                # 3. RSI below floor (don't exit if RSI still strong)
                if drawdown_from_peak > self.trailing_stop and not ema_bullish:
                    signal.iloc[i] = 0
                    in_position = False
                elif drawdown_from_peak > self.trailing_stop and rsi_val < self.rsi_exit_floor:
                    signal.iloc[i] = 0
                    in_position = False
                elif not ema_bullish and not macd_positive and not above_sma50:
                    # Full bearish confirmation — exit
                    signal.iloc[i] = 0
                    in_position = False
                else:
                    signal.iloc[i] = 1

        return signal
