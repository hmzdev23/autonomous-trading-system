"""
Live Signal Engine.

Reuses the exact same strategy code from backtesting to generate
real-time trading signals and target portfolio weights.
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from data.fetcher import fetch_single
from data.processor import add_indicators
from strategies.registry import get_strategy_for_ticker
from portfolio.momentum_allocator import MomentumWeightedAllocator
from utils.logger import get_logger

log = get_logger(__name__)

# Tickers excluded from live trading
EXCLUDED_LIVE = {'ZEB'}  # Canadian ETF, not tradable on Alpaca


def get_live_tickers() -> list:
    """Return tickers eligible for live trading (excludes ZEB etc.)."""
    return [t for t in config.ALL_TICKERS if t not in EXCLUDED_LIVE]


def generate_signals(tickers: list = None, lookback_days: int = 300) -> dict:
    """
    Generate current trading signals for all tickers.

    Uses the same strategy code as the backtester:
    1. Fetch recent historical data (last ~300 days for indicator warmup)
    2. Compute indicators
    3. Run each ticker's assigned strategy
    4. Return current signal (1 = long, 0 = flat)

    Returns:
        dict with keys: signals, weights, targets
    """
    tickers = tickers or get_live_tickers()
    end = datetime.now().strftime('%Y-%m-%d')
    start = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

    log.info(f"Generating live signals for {len(tickers)} tickers...")
    log.info(f"Data window: {start} → {end}")

    # ── Step 1: Fetch data ───────────────────────────────────────────────
    data = {}
    failed = []
    for ticker in tickers:
        try:
            df = fetch_single(ticker, start, end)
            if df is not None and len(df) > 50:
                data[ticker] = df
            else:
                failed.append(ticker)
                log.warning(f"  {ticker}: Insufficient data ({len(df) if df is not None else 0} rows)")
        except Exception as e:
            failed.append(ticker)
            log.warning(f"  {ticker}: Fetch failed — {e}")

    if failed:
        log.warning(f"Failed tickers: {failed}")

    active_tickers = list(data.keys())
    log.info(f"Active tickers: {len(active_tickers)}/{len(tickers)}")

    # ── Step 2: Add indicators ───────────────────────────────────────────
    for ticker in active_tickers:
        data[ticker] = add_indicators(data[ticker])

    # ── Step 3: Generate per-ticker signals ──────────────────────────────
    signals = {}
    signal_details = {}

    for ticker in active_tickers:
        strategy = get_strategy_for_ticker(ticker)
        sig_series = strategy.generate_signals(data[ticker])

        # Get the most recent signal
        current_signal = int(sig_series.iloc[-1]) if len(sig_series) > 0 else 0
        signals[ticker] = current_signal

        # Activation stats (last 63 days)
        recent = sig_series.tail(63)
        activation = recent.mean() * 100 if len(recent) > 0 else 0

        signal_details[ticker] = {
            'signal': current_signal,
            'strategy': config.STRATEGY_ASSIGNMENTS.get(ticker, 'unknown'),
            'activation_pct': round(activation, 1),
            'last_price': round(float(data[ticker]['Close'].iloc[-1]), 2),
            'last_date': str(data[ticker].index[-1].date()),
        }

        status = "🟢 LONG" if current_signal == 1 else "⚪ FLAT"
        log.info(f"  {ticker:5s} → {status}  ({signal_details[ticker]['strategy']}, "
                 f"{activation:.0f}% active)")

    # ── Step 4: Compute target weights ───────────────────────────────────
    allocator = MomentumWeightedAllocator()

    # Build price matrix for allocator
    close_prices = pd.DataFrame(
        {t: data[t]['Close'] for t in active_tickers}
    ).sort_index().dropna(how='all')

    # Compute raw weights
    today = close_prices.index[-1]
    raw_weights = allocator.compute_weights(close_prices, today)

    # Apply signal filter: zero weight for tickers with flat signal
    target_weights = {}
    for ticker, weight in raw_weights.items():
        if signals.get(ticker, 0) == 1:
            target_weights[ticker] = weight
        else:
            target_weights[ticker] = 0.0

    # Re-normalize non-zero weights so they sum to 1 (or less if many flat)
    total = sum(target_weights.values())
    if total > 0:
        # Scale up invested portion, but cap at 100%
        scale = min(1.0 / total, 1.5)  # Allow up to 1.5x scaling
        target_weights = {t: w * scale for t, w in target_weights.items()}
        # Re-cap individual weights
        for t in target_weights:
            target_weights[t] = min(target_weights[t], config.MAX_TICKER_WEIGHT)

    # Calculate invested %
    invested_pct = sum(target_weights.values()) * 100

    log.info(f"\nTarget allocation: {invested_pct:.1f}% invested, "
             f"{100 - invested_pct:.1f}% cash")
    log.info(f"Active positions: {sum(1 for s in signals.values() if s == 1)}"
             f"/{len(signals)}")

    return {
        'signals': signals,
        'signal_details': signal_details,
        'target_weights': target_weights,
        'invested_pct': invested_pct,
        'active_tickers': active_tickers,
        'failed_tickers': failed,
        'timestamp': datetime.now().isoformat(),
    }


def compute_target_positions(signal_result: dict, portfolio_value: float) -> dict:
    """
    Convert target weights to dollar amounts.

    Args:
        signal_result: Output from generate_signals()
        portfolio_value: Current portfolio value in dollars

    Returns:
        dict of {ticker: target_dollar_value}
    """
    targets = {}
    for ticker, weight in signal_result['target_weights'].items():
        dollar_target = portfolio_value * weight
        targets[ticker] = round(dollar_target, 2)

    return targets
