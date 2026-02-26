"""
Data quality validation utilities.
"""

import pandas as pd
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)


def validate_ohlcv(df: pd.DataFrame, ticker: str) -> dict:
    """
    Validate OHLCV data quality for a single ticker.
    Returns a dict of quality metrics.
    """
    report = {
        'ticker': ticker,
        'rows': len(df),
        'start': str(df.index.min().date()) if len(df) > 0 else 'N/A',
        'end': str(df.index.max().date()) if len(df) > 0 else 'N/A',
        'nan_counts': {},
        'consecutive_nans': 0,
        'issues': [],
    }

    if len(df) == 0:
        report['issues'].append('NO DATA')
        return report

    # Check NaN counts per column
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            nan_count = df[col].isna().sum()
            report['nan_counts'][col] = int(nan_count)
            if nan_count > 0:
                report['issues'].append(f'{col}: {nan_count} NaNs')

    # Check consecutive NaNs in Close
    if 'Close' in df.columns:
        is_nan = df['Close'].isna()
        if is_nan.any():
            groups = (is_nan != is_nan.shift()).cumsum()
            max_consecutive = is_nan.groupby(groups).sum().max()
            report['consecutive_nans'] = int(max_consecutive)
            if max_consecutive > 5:
                report['issues'].append(
                    f'WARNING: {max_consecutive} consecutive NaN days in Close'
                )

    # Check for zero/negative prices
    if 'Close' in df.columns:
        non_positive = (df['Close'] <= 0).sum()
        if non_positive > 0:
            report['issues'].append(f'{non_positive} non-positive Close prices')

    return report


def print_quality_report(reports: list[dict]) -> None:
    """Print a formatted data quality report for all tickers."""
    log.info("=" * 80)
    log.info("DATA QUALITY REPORT")
    log.info("=" * 80)
    log.info(f"{'Ticker':<8} {'Rows':>6} {'Start':<12} {'End':<12} {'NaN Close':>10} {'Issues'}")
    log.info("-" * 80)

    for r in reports:
        nan_close = r['nan_counts'].get('Close', 0)
        issues = '; '.join(r['issues']) if r['issues'] else 'OK'
        log.info(
            f"{r['ticker']:<8} {r['rows']:>6} {r['start']:<12} {r['end']:<12} "
            f"{nan_close:>10} {issues}"
        )

    log.info("=" * 80)
