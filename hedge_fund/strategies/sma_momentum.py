"""
SMA Momentum Strategy — PDF §3.12: Two Moving Average Crossover

Entry: Long when SMA(fast) crosses above SMA(slow)  [Golden Cross]
Exit:  Flat when SMA(fast) crosses below SMA(slow)  [Death Cross]
Stop:  Liquidate if price falls > stop_loss% below entry price

From PDF Eq. 322-323:
    Signal = LONG  if MA(T') > MA(T)      [fast > slow]
    Signal = FLAT  if MA(T') < MA(T)      [fast < slow]
    Stop:  Liquidate if P < (1 - Δ) × P_entry
"""

import pandas as pd
import numpy as np
from strategies.base import Strategy


class SMAMomentumStrategy(Strategy):
    """
    Two Moving Average Crossover with stop-loss.

    Assigned to: VOO, QQQ, AAPL, MSFT, NVDA, GOOGL, AMZN, TSLA
    """

    def __init__(self, fast: int = 50, slow: int = 200,
                 stop_loss: float = 0.08):
        super().__init__(
            name='sma_momentum',
            params={
                'fast': fast,
                'slow': slow,
                'stop_loss': stop_loss,
            }
        )
        self.fast = fast
        self.slow = slow
        self.stop_loss = stop_loss

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate SMA crossover signals.
        No lookahead: signal[i] uses data up to and including day i.
        """
        close = df['Close']
        sma_fast_key = f'SMA_{self.fast}'
        sma_slow_key = f'SMA_{self.slow}'

        # Ensure indicators exist
        if sma_fast_key not in df.columns or sma_slow_key not in df.columns:
            raise ValueError(
                f"Missing {sma_fast_key} or {sma_slow_key}. "
                f"Run processor.add_indicators() first."
            )

        sma_fast = df[sma_fast_key]
        sma_slow = df[sma_slow_key]

        # Base signal: 1 when fast > slow, 0 otherwise
        raw_signal = (sma_fast > sma_slow).astype(int)

        # Apply stop-loss: track entry price and exit if drawdown too deep
        signal = pd.Series(0, index=df.index, dtype=int)
        in_position = False
        entry_price = 0.0

        for i in range(len(df)):
            if np.isnan(sma_fast.iloc[i]) or np.isnan(sma_slow.iloc[i]):
                signal.iloc[i] = 0
                continue

            if not in_position:
                if raw_signal.iloc[i] == 1:
                    # Enter position
                    signal.iloc[i] = 1
                    in_position = True
                    entry_price = close.iloc[i]
                else:
                    signal.iloc[i] = 0
            else:
                # Check stop-loss
                if close.iloc[i] < entry_price * (1 - self.stop_loss):
                    # Stop-loss triggered
                    signal.iloc[i] = 0
                    in_position = False
                elif raw_signal.iloc[i] == 0:
                    # Death cross — exit
                    signal.iloc[i] = 0
                    in_position = False
                else:
                    # Stay in position
                    signal.iloc[i] = 1

        return signal
