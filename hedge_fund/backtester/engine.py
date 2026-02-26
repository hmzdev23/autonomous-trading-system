"""
Vectorised multi-asset backtesting engine.

Handles all 20 tickers simultaneously with:
- Per-ticker strategy assignment (from registry)
- Inverse-vol allocation with monthly rebalancing
- No lookahead bias (signals on day N → trades at open N+1)
- Benchmark tracking (buy-and-hold VOO)
"""

import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from data.fetcher import fetch_historical
from data.processor import add_indicators, add_benchmark_correlation
from strategies.registry import get_strategy_for_ticker
from portfolio.allocator import InverseVolAllocator
from portfolio.momentum_allocator import MomentumWeightedAllocator
from backtester.metrics import compute_metrics, print_metrics
from utils.logger import get_logger

log = get_logger(__name__)


class BacktestEngine:
    """
    Multi-asset backtester with strategy-per-ticker and configurable allocation.
    """

    def __init__(self,
                 tickers: list[str] = None,
                 start: str = None,
                 end: str = None,
                 capital: float = None,
                 slippage: float = None,
                 commission: float = None):
        self.tickers = tickers or config.ALL_TICKERS
        self.start = start or config.BACKTEST_START
        self.end = end or config.BACKTEST_END
        self.capital = capital or config.STARTING_CAPITAL
        self.slippage = slippage or config.SLIPPAGE
        self.commission = commission or config.COMMISSION

        # Select allocator based on config
        if getattr(config, 'ALLOCATION_MODE', 'inverse_vol') == 'momentum':
            self.allocator = MomentumWeightedAllocator()
            log.info("Using MOMENTUM-WEIGHTED allocation")
        else:
            self.allocator = InverseVolAllocator()
            log.info("Using INVERSE-VOLATILITY allocation")

    def run(self) -> dict:
        """
        Run the full backtest.

        Returns dict with:
            - 'portfolio_metrics': overall portfolio metrics
            - 'benchmark_metrics': VOO buy-and-hold metrics
            - 'per_ticker': {ticker: metrics dict}
            - 'equity_curve': pd.Series
            - 'benchmark_curve': pd.Series
            - 'weight_history': pd.DataFrame
            - 'signals': {ticker: pd.Series}
            - 'all_data': {ticker: pd.DataFrame}
        """
        log.info("=" * 70)
        log.info("BACKTEST ENGINE — Starting")
        log.info(f"  Tickers: {len(self.tickers)}")
        log.info(f"  Period:  {self.start} → {self.end}")
        log.info(f"  Capital: ${self.capital:,.0f}")
        log.info("=" * 70)

        # ── Step 1: Fetch Data ───────────────────────────────────────────
        log.info("\n[1/5] Fetching data...")
        raw_data = fetch_historical(self.tickers, self.start, self.end)

        # Filter out tickers with no data
        data = {}
        for t in self.tickers:
            if t in raw_data and len(raw_data[t]) > 0:
                data[t] = raw_data[t]
            else:
                log.warning(f"  Skipping {t} — no data available")

        active_tickers = list(data.keys())
        log.info(f"  Active tickers: {len(active_tickers)}/{len(self.tickers)}")

        # ── Step 2: Add Indicators ───────────────────────────────────────
        log.info("\n[2/5] Computing indicators...")
        for t in active_tickers:
            data[t] = add_indicators(data[t])

        # Add benchmark correlation
        if config.BENCHMARK in data:
            bench_returns = data[config.BENCHMARK]['Close'].pct_change()
            for t in active_tickers:
                if t != config.BENCHMARK:
                    data[t] = add_benchmark_correlation(data[t], bench_returns)

        # ── Step 3: Generate Signals ─────────────────────────────────────
        log.info("\n[3/5] Generating signals...")
        signals = {}
        for t in active_tickers:
            try:
                strategy = get_strategy_for_ticker(t)
                sig = strategy.generate_signals(data[t])
                signals[t] = sig
                active_pct = (sig == 1).sum() / len(sig) * 100
                log.info(f"  {t:5s} → {strategy.name:20s} | "
                         f"Active: {active_pct:.1f}% of days")
            except Exception as e:
                log.error(f"  {t}: Signal generation failed — {e}")
                signals[t] = pd.Series(0, index=data[t].index)

        # ── Step 4: Build Price Matrix ───────────────────────────────────
        log.info("\n[4/5] Running backtest simulation...")

        # Create aligned close price matrix
        close_prices = pd.DataFrame(
            {t: data[t]['Close'] for t in active_tickers}
        )
        close_prices = close_prices.sort_index().dropna(how='all')

        # Open prices for trade execution (next-day open)
        open_prices = pd.DataFrame(
            {t: data[t]['Open'] for t in active_tickers
             if 'Open' in data[t].columns}
        )
        open_prices = open_prices.reindex(close_prices.index)

        # Align signals to the close price matrix index
        signal_matrix = pd.DataFrame(index=close_prices.index)
        for t in active_tickers:
            sig = signals[t].reindex(close_prices.index, fill_value=0)
            signal_matrix[t] = sig

        # ── Step 5: Compute Portfolio Returns ────────────────────────────
        # Weight computation at rebalance dates
        rebal_dates = self.allocator.get_rebalance_dates(
            self.start, self.end, close_prices.index
        )

        # Build daily weight matrix
        weight_matrix = pd.DataFrame(0.0, index=close_prices.index,
                                     columns=active_tickers)

        current_weights = {}
        for i, date in enumerate(close_prices.index):
            # Rebalance check
            if date in rebal_dates:
                current_weights = self.allocator.compute_weights(
                    close_prices, date
                )

            # Apply weights
            for t in active_tickers:
                weight_matrix.loc[date, t] = current_weights.get(t, 0)

        # Effective allocation = target_weight × strategy_signal
        # Signal from yesterday → trade at today's open
        shifted_signals = signal_matrix.shift(1).fillna(0)
        effective_weights = weight_matrix * shifted_signals

        # Normalize: if some signals are 0, weight goes to cash (not redistributed)
        # So total invested = sum of effective weights (≤ 1.0)

        # Daily returns
        daily_returns = close_prices.pct_change(fill_method=None)

        # Account for slippage on signal changes
        signal_changes = shifted_signals.diff().fillna(0).abs()
        slippage_cost = signal_changes * self.slippage

        # Portfolio return: weighted sum of individual returns minus slippage
        portfolio_return = (effective_weights * daily_returns).sum(axis=1) \
                           - (effective_weights * slippage_cost).sum(axis=1)

        # Build equity curve
        equity_curve = (1 + portfolio_return).cumprod() * self.capital
        equity_curve.name = 'Portfolio'

        # Benchmark: buy-and-hold VOO
        if config.BENCHMARK in data:
            bench_close = data[config.BENCHMARK]['Close']
            bench_close = bench_close.loc[bench_close.index.isin(close_prices.index)]
            benchmark_curve = bench_close / bench_close.iloc[0] * self.capital
            benchmark_curve.name = 'Benchmark (VOO)'
        else:
            benchmark_curve = pd.Series(self.capital, index=close_prices.index)

        # ── Step 6: Compute Metrics ──────────────────────────────────────
        log.info("\n[5/5] Computing metrics...")

        # Overall portfolio metrics
        portfolio_metrics = compute_metrics(
            equity_curve,
            benchmark_series=benchmark_curve,
        )

        # Benchmark metrics
        benchmark_metrics = compute_metrics(benchmark_curve)

        # Per-ticker metrics
        per_ticker = {}
        for t in active_tickers:
            t_returns = daily_returns[t] * shifted_signals[t]
            t_equity = (1 + t_returns.fillna(0)).cumprod() * (
                self.capital * weight_matrix[t].mean()
            )
            if t_equity.iloc[0] > 0:
                per_ticker[t] = compute_metrics(t_equity, benchmark_curve)
                per_ticker[t]['strategy'] = config.STRATEGY_ASSIGNMENTS.get(t, 'unknown')
                per_ticker[t]['avg_weight'] = weight_matrix[t].mean()

        # Print summary
        print_metrics(portfolio_metrics, title=config.FUND_NAME)

        log.info(f"\nBenchmark (VOO) Total Return: "
                 f"{benchmark_metrics.get('total_return_pct', 0):.2f}%")
        log.info(f"Benchmark Sharpe: "
                 f"{benchmark_metrics.get('sharpe_ratio', 0):.3f}")

        results = {
            'portfolio_metrics': portfolio_metrics,
            'benchmark_metrics': benchmark_metrics,
            'per_ticker': per_ticker,
            'equity_curve': equity_curve,
            'benchmark_curve': benchmark_curve,
            'weight_history': weight_matrix,
            'signals': signals,
            'all_data': data,
            'active_tickers': active_tickers,
        }

        return results


def run_backtest(**kwargs) -> dict:
    """Convenience function to run a backtest."""
    engine = BacktestEngine(**kwargs)
    return engine.run()
