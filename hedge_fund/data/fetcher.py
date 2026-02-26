"""
Historical data fetching with caching.
Supports yfinance for historical data with Parquet caching.
"""

import os
import pandas as pd
import yfinance as yf
from utils.logger import get_logger
from utils.validators import validate_ohlcv, print_quality_report

log = get_logger(__name__)

# Ticker aliases for non-standard yfinance symbols
TICKER_ALIASES = {
    'ZEB': 'ZEB.TO',
}

CACHE_DIR = os.path.join(os.path.dirname(__file__), 'cache')


def _get_yf_ticker(ticker: str) -> str:
    """Get the yfinance-compatible ticker symbol."""
    return TICKER_ALIASES.get(ticker, ticker)


def _cache_path(ticker: str, start: str, end: str) -> str:
    """Get the cache file path for a ticker."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f'{ticker}_{start}_{end}.parquet')


def fetch_single(ticker: str, start: str, end: str,
                 use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch OHLCV data for a single ticker.
    Uses Parquet cache if available.
    """
    cache_file = _cache_path(ticker, start, end)

    # Try cache first
    if use_cache and os.path.exists(cache_file):
        log.info(f"  {ticker}: Loading from cache")
        df = pd.read_parquet(cache_file)
        return df

    # Download from yfinance
    yf_ticker = _get_yf_ticker(ticker)
    log.info(f"  {ticker}: Downloading from yfinance (symbol: {yf_ticker})")

    try:
        data = yf.download(
            yf_ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
        )

        if data.empty:
            log.warning(f"  {ticker}: No data returned from yfinance")
            return pd.DataFrame()

        # Flatten multi-level columns if present
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Ensure standard column names
        data = data.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume'
        })

        # Keep only OHLCV
        cols = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume']
                if c in data.columns]
        data = data[cols]

        # Forward-fill small gaps (weekends/holidays already excluded)
        data = data.ffill(limit=3)

        # Save to cache
        data.to_parquet(cache_file)
        log.info(f"  {ticker}: Downloaded {len(data)} rows, cached")

        return data

    except Exception as e:
        log.error(f"  {ticker}: Download failed — {e}")
        return pd.DataFrame()


def fetch_historical(tickers: list[str], start: str, end: str,
                     source: str = 'yfinance',
                     use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """
    Download OHLCV for all tickers.
    Returns dict of {ticker: DataFrame}.
    Prints data quality report.
    """
    log.info(f"Fetching data for {len(tickers)} tickers: {start} to {end}")

    data = {}
    reports = []

    for ticker in tickers:
        df = fetch_single(ticker, start, end, use_cache=use_cache)
        data[ticker] = df
        report = validate_ohlcv(df, ticker)
        reports.append(report)

    print_quality_report(reports)

    # Summary
    ok_count = sum(1 for r in reports if not r['issues'])
    log.info(f"\n{ok_count}/{len(tickers)} tickers clean, "
             f"{len(tickers) - ok_count} with issues")

    return data
