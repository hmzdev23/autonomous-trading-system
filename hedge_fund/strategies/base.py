"""
Abstract base class for all trading strategies.
"""

from abc import ABC, abstractmethod
import pandas as pd


class Strategy(ABC):
    """
    Base class for all trading strategies.

    Each strategy takes a DataFrame with OHLCV + indicators
    and produces a signal Series:
        1 = LONG (fully invested)
        0 = FLAT (in cash)
       -1 = SHORT (if allowed)
    """

    def __init__(self, name: str, params: dict = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals from a DataFrame.

        Args:
            df: DataFrame with OHLCV data and indicators (from processor.py)

        Returns:
            pd.Series of signals (1, 0, -1) indexed by date.
            Signal on day N uses only data through day N.
            Trade executes at open of day N+1.
        """
        pass

    def get_params(self) -> dict:
        """Return current strategy parameters."""
        return self.params.copy()

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', params={self.params})"
