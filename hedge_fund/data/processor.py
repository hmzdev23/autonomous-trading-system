"""
Technical indicator computation and feature engineering.
All indicators computed without lookahead bias using pandas/numpy.
"""

import pandas as pd
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def bollinger_bands(series: pd.Series, window: int = 20,
                    num_std: float = 2.0) -> tuple:
    """Bollinger Bands: (upper, middle, lower)."""
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1/window, min_periods=window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple:
    """MACD: (line, signal, histogram)."""
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        window: int = 14) -> pd.Series:
    """Average True Range."""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=window, min_periods=window).mean()


def z_score(series: pd.Series, window: int = 20) -> pd.Series:
    """Rolling Z-score of price."""
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    rolling_std = series.rolling(window=window, min_periods=window).std()
    return (series - rolling_mean) / rolling_std


def rolling_volatility(returns: pd.Series, window: int = 60) -> pd.Series:
    """Annualised rolling volatility."""
    return returns.rolling(window=window, min_periods=window).std() * np.sqrt(252)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all technical indicators needed across all strategies.
    All computed without lookahead bias (using only past data).

    Input df must have columns: Open, High, Low, Close, Volume
    """
    df = df.copy()
    close = df['Close']

    # ── Moving Averages ──────────────────────────────────────────────────
    for w in [20, 50, 100, 200]:
        df[f'SMA_{w}'] = sma(close, w)

    df['EMA_12'] = ema(close, 12)
    df['EMA_26'] = ema(close, 26)

    # ── MACD ─────────────────────────────────────────────────────────────
    df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = macd(close)

    # ── RSI ──────────────────────────────────────────────────────────────
    df['RSI_14'] = rsi(close, 14)

    # ── Bollinger Bands ──────────────────────────────────────────────────
    df['BB_Upper'], df['BB_Mid'], df['BB_Lower'] = bollinger_bands(close)

    # ── ATR ──────────────────────────────────────────────────────────────
    df['ATR_14'] = atr(df['High'], df['Low'], close, 14)

    # ── Returns ─────────────────────────────────────────────────────────
    df['Return'] = close.pct_change()
    df['Log_Return'] = np.log(close / close.shift(1))

    # ── Rolling Volatility ──────────────────────────────────────────────
    df['Vol_20'] = rolling_volatility(df['Return'], 20)
    df['Vol_60'] = rolling_volatility(df['Return'], 60)

    # ── Z-Score ─────────────────────────────────────────────────────────
    df['Z_Score_20'] = z_score(close, 20)

    # ── Volume MA ────────────────────────────────────────────────────────
    df['Volume_MA_20'] = sma(df['Volume'], 20)

    # ── Cumulative Return (for sector momentum) ─────────────────────────
    df['Cum_Return_126'] = close.pct_change(126)  # ~6 months

    return df


def add_benchmark_correlation(df: pd.DataFrame,
                              benchmark_returns: pd.Series,
                              window: int = 60) -> pd.DataFrame:
    """Add rolling correlation with benchmark (VOO)."""
    df = df.copy()
    if 'Return' not in df.columns:
        df['Return'] = df['Close'].pct_change()

    # Align on common index
    common_idx = df.index.intersection(benchmark_returns.index)
    if len(common_idx) > window:
        aligned_ret = df.loc[common_idx, 'Return']
        aligned_bench = benchmark_returns.loc[common_idx]
        df.loc[common_idx, 'Corr_VOO_60'] = (
            aligned_ret.rolling(window=window, min_periods=window)
            .corr(aligned_bench)
        )
    else:
        df['Corr_VOO_60'] = np.nan

    return df
