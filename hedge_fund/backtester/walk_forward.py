"""
Walk-forward validation to detect overfitting.
Rolling train/test windows to evaluate strategy robustness.
"""

import pandas as pd
import numpy as np
from backtester.metrics import compute_metrics
from utils.logger import get_logger

log = get_logger(__name__)


def walk_forward_validate(equity_curve: pd.Series,
                          train_months: int = 6,
                          test_months: int = 6) -> dict:
    """
    Walk-forward validation with rolling windows.

    Splits equity curve into train/test windows and compares
    in-sample vs out-of-sample Sharpe ratios.

    Returns dict with validation results.
    """
    returns = equity_curve.pct_change().dropna()

    if len(returns) < 252:  # Need at least 1 year
        return {'error': 'Insufficient data for walk-forward validation'}

    train_days = train_months * 21  # ~21 trading days per month
    test_days = test_months * 21
    window_size = train_days + test_days

    results = []
    i = 0

    while i + window_size <= len(returns):
        train_ret = returns.iloc[i:i + train_days]
        test_ret = returns.iloc[i + train_days:i + window_size]

        train_sharpe = (train_ret.mean() / train_ret.std() * np.sqrt(252)
                        if train_ret.std() > 0 else 0)
        test_sharpe = (test_ret.mean() / test_ret.std() * np.sqrt(252)
                       if test_ret.std() > 0 else 0)

        results.append({
            'window': len(results) + 1,
            'train_start': train_ret.index[0].strftime('%Y-%m-%d'),
            'train_end': train_ret.index[-1].strftime('%Y-%m-%d'),
            'test_start': test_ret.index[0].strftime('%Y-%m-%d'),
            'test_end': test_ret.index[-1].strftime('%Y-%m-%d'),
            'train_sharpe': round(train_sharpe, 3),
            'test_sharpe': round(test_sharpe, 3),
            'degradation_pct': round(
                (1 - test_sharpe / train_sharpe) * 100, 1
            ) if train_sharpe > 0 else 0,
        })

        i += test_days  # Slide forward by test window

    # Summary
    if not results:
        return {'error': 'No complete windows found'}

    train_sharpes = [r['train_sharpe'] for r in results]
    test_sharpes = [r['test_sharpe'] for r in results]
    avg_degradation = np.mean([r['degradation_pct'] for r in results])

    # Flag overfitting if >50% Sharpe drop
    overfitting_warning = avg_degradation > 50

    log.info("\n" + "=" * 70)
    log.info("WALK-FORWARD VALIDATION")
    log.info("=" * 70)
    for r in results:
        flag = " ⚠️ OVERFIT" if r['degradation_pct'] > 50 else ""
        log.info(
            f"  Window {r['window']}: "
            f"Train Sharpe={r['train_sharpe']:.3f} | "
            f"Test Sharpe={r['test_sharpe']:.3f} | "
            f"Degradation={r['degradation_pct']:.1f}%{flag}"
        )

    log.info(f"\n  Avg Train Sharpe: {np.mean(train_sharpes):.3f}")
    log.info(f"  Avg Test Sharpe:  {np.mean(test_sharpes):.3f}")
    log.info(f"  Avg Degradation:  {avg_degradation:.1f}%")

    if overfitting_warning:
        log.warning("  ⚠️  POTENTIAL OVERFITTING DETECTED "
                     "(>50% average Sharpe degradation)")
    else:
        log.info("  ✓ No significant overfitting detected")

    log.info("=" * 70)

    return {
        'windows': results,
        'avg_train_sharpe': round(np.mean(train_sharpes), 3),
        'avg_test_sharpe': round(np.mean(test_sharpes), 3),
        'avg_degradation_pct': round(avg_degradation, 1),
        'overfitting_warning': overfitting_warning,
    }
