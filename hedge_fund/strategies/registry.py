"""
Strategy Registry — maps strategy names to classes and tickers to strategies.
"""

from strategies.base import Strategy
from strategies.sma_momentum import SMAMomentumStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.sector_momentum import SectorMomentumStrategy
from strategies.aggressive_momentum import AggressiveMomentumStrategy
from strategies.dual_momentum import DualMomentumStrategy
from strategies.leveraged_momentum import LeveragedMomentumStrategy
import config


# Strategy class registry
STRATEGY_CLASSES = {
    'sma_momentum': SMAMomentumStrategy,
    'mean_reversion': MeanReversionStrategy,
    'sector_momentum': SectorMomentumStrategy,
    'aggressive_momentum': AggressiveMomentumStrategy,
    'dual_momentum': DualMomentumStrategy,
    'leveraged_momentum': LeveragedMomentumStrategy,
}


def get_strategy(name: str, **kwargs) -> Strategy:
    """Get a strategy instance by name."""
    if name not in STRATEGY_CLASSES:
        raise ValueError(
            f"Unknown strategy: {name}. "
            f"Available: {list(STRATEGY_CLASSES.keys())}"
        )
    return STRATEGY_CLASSES[name](**kwargs)


def get_strategy_for_ticker(ticker: str) -> Strategy:
    """
    Get the assigned strategy for a ticker, with proper parameters.
    """
    strategy_name = config.STRATEGY_ASSIGNMENTS.get(ticker)
    if strategy_name is None:
        raise ValueError(f"No strategy assigned to ticker: {ticker}")

    if strategy_name == 'aggressive_momentum':
        return AggressiveMomentumStrategy(
            ema_fast=config.AGG_EMA_FAST,
            ema_slow=config.AGG_EMA_SLOW,
            trailing_stop=config.AGG_TRAILING_STOP,
            rsi_exit_floor=config.AGG_RSI_EXIT_FLOOR,
        )

    elif strategy_name == 'dual_momentum':
        return DualMomentumStrategy(
            lookback=config.DUAL_LOOKBACK,
            min_lookback=config.DUAL_MIN_LOOKBACK,
            trend_filter=config.DUAL_TREND_FILTER,
        )

    elif strategy_name == 'sector_momentum':
        return SectorMomentumStrategy(
            lookback=config.SM_LOOKBACK,
            ma_filter=config.SM_MA_FILTER,
            top_fraction=config.SM_TOP_FRACTION,
        )

    elif strategy_name == 'sma_momentum':
        stop_loss = config.SMA_STOP_LOSS
        if ticker in config.HIGH_VOL_TICKERS:
            stop_loss = config.SMA_STOP_LOSS_HIGH_VOL
        return SMAMomentumStrategy(
            fast=config.SMA_FAST,
            slow=config.SMA_SLOW,
            stop_loss=stop_loss,
        )

    elif strategy_name == 'mean_reversion':
        return MeanReversionStrategy(
            lookback=config.MR_LOOKBACK,
            entry_z=config.MR_ENTRY_Z,
            exit_z=config.MR_EXIT_Z,
            max_hold=config.MR_MAX_HOLD,
            stop_loss=config.MR_STOP_LOSS,
            allow_short=config.MR_ALLOW_SHORT,
        )

    elif strategy_name == 'leveraged_momentum':
        return LeveragedMomentumStrategy(
            ema_fast=5,
            ema_slow=13,
            trailing_stop=config.LEVERAGED_TRAILING_STOP,
            max_hold_days=config.LEVERAGED_MAX_HOLD_DAYS,
        )

    else:
        return get_strategy(strategy_name)


def get_all_assignments() -> dict[str, str]:
    """Return the full ticker → strategy_name mapping."""
    return config.STRATEGY_ASSIGNMENTS.copy()
