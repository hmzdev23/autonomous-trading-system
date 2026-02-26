"""
Performance metrics for backtesting.
Computes returns, risk, and trade statistics.
"""

import pandas as pd
import numpy as np
from utils.logger import get_logger

log = get_logger(__name__)

RISK_FREE_RATE = 0.03  # 3% annual


def compute_metrics(equity_series: pd.Series,
                    benchmark_series: pd.Series = None,
                    trade_df: pd.DataFrame = None,
                    risk_free_rate: float = RISK_FREE_RATE) -> dict:
    """
    Compute comprehensive performance metrics.

    Args:
        equity_series: Daily portfolio equity values
        benchmark_series: Daily benchmark equity values (optional)
        trade_df: DataFrame of trades (optional)
        risk_free_rate: Annual risk-free rate

    Returns:
        Dict of all computed metrics
    """
    if len(equity_series) < 2:
        return {'error': 'Insufficient data'}

    returns = equity_series.pct_change().dropna()
    daily_rf = (1 + risk_free_rate) ** (1/252) - 1

    # ── Returns ──────────────────────────────────────────────────────────
    total_return = (equity_series.iloc[-1] / equity_series.iloc[0]) - 1
    n_years = len(returns) / 252
    cagr = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

    # Monthly returns
    monthly_equity = equity_series.resample('ME').last().dropna()
    monthly_returns = monthly_equity.pct_change().dropna()

    best_month = monthly_returns.max() if len(monthly_returns) > 0 else 0
    worst_month = monthly_returns.min() if len(monthly_returns) > 0 else 0

    # Annual returns
    annual_equity = equity_series.resample('YE').last().dropna()
    annual_returns = annual_equity.pct_change().dropna()
    annual_returns_dict = {
        d.year: round(r * 100, 2)
        for d, r in annual_returns.items()
    }

    # ── Risk ─────────────────────────────────────────────────────────────
    vol = returns.std() * np.sqrt(252)

    # Max Drawdown
    cummax = equity_series.cummax()
    drawdown = (equity_series - cummax) / cummax
    max_dd = drawdown.min()

    # Max drawdown duration
    in_drawdown = drawdown < 0
    if in_drawdown.any():
        dd_groups = (~in_drawdown).cumsum()
        dd_durations = in_drawdown.groupby(dd_groups).sum()
        max_dd_duration = int(dd_durations.max())
    else:
        max_dd_duration = 0

    # VaR and CVaR (95%)
    var_95 = np.percentile(returns, 5)
    cvar_95 = returns[returns <= var_95].mean() if (returns <= var_95).any() else var_95

    # ── Risk-Adjusted ────────────────────────────────────────────────────
    excess_returns = returns - daily_rf
    sharpe = excess_returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0

    # Sortino
    downside = returns[returns < 0]
    downside_std = downside.std() if len(downside) > 0 else 0
    sortino = excess_returns.mean() / downside_std * np.sqrt(252) if downside_std > 0 else 0

    # Calmar
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0

    # ── Benchmark Comparison ──────────────────────────────────────────────
    info_ratio = 0
    beta = 0
    alpha = 0
    corr = 0

    if benchmark_series is not None and len(benchmark_series) > 1:
        bench_returns = benchmark_series.pct_change().dropna()

        # Align
        common = returns.index.intersection(bench_returns.index)
        if len(common) > 10:
            r_aligned = returns.loc[common]
            b_aligned = bench_returns.loc[common]

            # Information ratio
            tracking = (r_aligned - b_aligned)
            info_ratio = tracking.mean() / tracking.std() * np.sqrt(252) \
                if tracking.std() > 0 else 0

            # Beta
            cov = np.cov(r_aligned, b_aligned)
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0

            # Alpha (annualized Jensen's alpha)
            bench_return = (benchmark_series.iloc[-1] / benchmark_series.iloc[0]) - 1
            bench_cagr = (1 + bench_return) ** (1 / n_years) - 1 if n_years > 0 else 0
            alpha = cagr - (risk_free_rate + beta * (bench_cagr - risk_free_rate))

            # Correlation
            corr = r_aligned.corr(b_aligned)

    # ── Trade Statistics ─────────────────────────────────────────────────
    trade_stats = _compute_trade_stats(trade_df) if trade_df is not None and len(trade_df) > 0 else {}

    return {
        # Returns
        'total_return_pct': round(total_return * 100, 2),
        'annualised_return_pct': round(cagr * 100, 2),
        'best_month_pct': round(best_month * 100, 2),
        'worst_month_pct': round(worst_month * 100, 2),
        'annual_returns': annual_returns_dict,
        'monthly_returns': monthly_returns,

        # Risk
        'volatility_ann_pct': round(vol * 100, 2),
        'max_drawdown_pct': round(max_dd * 100, 2),
        'max_drawdown_duration': max_dd_duration,
        'var_95_pct': round(var_95 * 100, 4),
        'cvar_95_pct': round(cvar_95 * 100, 4),

        # Risk-adjusted
        'sharpe_ratio': round(sharpe, 3),
        'sortino_ratio': round(sortino, 3),
        'calmar_ratio': round(calmar, 3),
        'information_ratio': round(info_ratio, 3),

        # Benchmark
        'correlation_to_bench': round(corr, 3),
        'beta': round(beta, 3),
        'alpha_ann_pct': round(alpha * 100, 2),

        # Trades
        **trade_stats,

        # Equity & drawdown series for charting
        '_equity_series': equity_series,
        '_drawdown_series': drawdown,
        '_monthly_returns': monthly_returns,
    }


def _compute_trade_stats(trade_df: pd.DataFrame) -> dict:
    """Compute trade-level statistics from trade log."""
    if trade_df is None or len(trade_df) == 0:
        return {
            'total_trades': 0,
            'win_rate_pct': 0,
            'profit_factor': 0,
            'avg_win_pct': 0,
            'avg_loss_pct': 0,
            'avg_holding_days': 0,
        }

    total_trades = len(trade_df)

    # Pair up buys and sells for P&L
    buys = trade_df[trade_df['side'] == 'BUY']
    sells = trade_df[trade_df['side'] == 'SELL']

    # Simple trade P&L approximation
    if 'pnl' in trade_df.columns:
        winners = trade_df[trade_df['pnl'] > 0]
        losers = trade_df[trade_df['pnl'] <= 0]
        win_rate = len(winners) / len(trade_df) * 100 if len(trade_df) > 0 else 0
        gross_profit = winners['pnl'].sum() if len(winners) > 0 else 0
        gross_loss = abs(losers['pnl'].sum()) if len(losers) > 0 else 1
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        avg_win = winners['pnl'].mean() if len(winners) > 0 else 0
        avg_loss = losers['pnl'].mean() if len(losers) > 0 else 0
    else:
        win_rate = 0
        profit_factor = 0
        avg_win = 0
        avg_loss = 0

    return {
        'total_trades': total_trades,
        'win_rate_pct': round(win_rate, 1),
        'profit_factor': round(profit_factor, 2),
        'avg_win_pct': round(avg_win * 100, 2) if avg_win else 0,
        'avg_loss_pct': round(avg_loss * 100, 2) if avg_loss else 0,
        'avg_holding_days': 0,
    }


def print_metrics(metrics: dict, title: str = 'Portfolio'):
    """Pretty-print metrics to console."""
    log.info("=" * 60)
    log.info(f"  {title} — Performance Summary")
    log.info("=" * 60)
    log.info(f"  Total Return:     {metrics.get('total_return_pct', 0):>10.2f}%")
    log.info(f"  CAGR:             {metrics.get('annualised_return_pct', 0):>10.2f}%")
    log.info(f"  Sharpe Ratio:     {metrics.get('sharpe_ratio', 0):>10.3f}")
    log.info(f"  Sortino Ratio:    {metrics.get('sortino_ratio', 0):>10.3f}")
    log.info(f"  Max Drawdown:     {metrics.get('max_drawdown_pct', 0):>10.2f}%")
    log.info(f"  Volatility:       {metrics.get('volatility_ann_pct', 0):>10.2f}%")
    log.info(f"  Calmar Ratio:     {metrics.get('calmar_ratio', 0):>10.3f}")
    log.info(f"  Beta:             {metrics.get('beta', 0):>10.3f}")
    log.info(f"  Alpha:            {metrics.get('alpha_ann_pct', 0):>10.2f}%")
    log.info(f"  Info Ratio:       {metrics.get('information_ratio', 0):>10.3f}")
    log.info(f"  VaR (95%):        {metrics.get('var_95_pct', 0):>10.4f}%")
    log.info(f"  CVaR (95%):       {metrics.get('cvar_95_pct', 0):>10.4f}%")
    log.info(f"  Total Trades:     {metrics.get('total_trades', 0):>10d}")
    log.info(f"  Best Month:       {metrics.get('best_month_pct', 0):>10.2f}%")
    log.info(f"  Worst Month:      {metrics.get('worst_month_pct', 0):>10.2f}%")

    annual = metrics.get('annual_returns', {})
    if annual:
        log.info("  Annual Returns:")
        for year, ret in sorted(annual.items()):
            log.info(f"    {year}:          {ret:>10.2f}%")

    log.info("=" * 60)
