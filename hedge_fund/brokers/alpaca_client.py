"""
Alpaca Markets SDK Wrapper.

Handles paper/live trading connection, account info, positions, and order submission.
Uses alpaca-py SDK (>= 0.21).
"""

import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logger import get_logger

log = get_logger(__name__)

# Alpaca SDK imports
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderStatus, QueryOrderStatus
from alpaca.common.exceptions import APIError


# Tickers that cannot be traded on Alpaca (e.g., Canadian-listed)
NON_TRADABLE = {'ZEB'}


class AlpacaClient:
    """
    Wrapper around Alpaca's TradingClient for paper and live trading.
    """

    def __init__(self, api_key: str = None, secret_key: str = None,
                 paper: bool = None):
        self.api_key = api_key or config.ALPACA_API_KEY
        self.secret_key = secret_key or config.ALPACA_SECRET_KEY
        self.paper = paper if paper is not None else config.ALPACA_PAPER

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API keys not set. Add ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY to your .env file.\n"
                "Get keys at: https://app.alpaca.markets/"
            )

        self.client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )

        mode = "PAPER" if self.paper else "LIVE"
        log.info(f"Alpaca client initialized [{mode} TRADING]")

    # ── Account ──────────────────────────────────────────────────────────────

    def get_account(self) -> dict:
        """Get account summary: equity, cash, buying power, P&L."""
        acct = self.client.get_account()
        return {
            'equity': float(acct.equity),
            'cash': float(acct.cash),
            'buying_power': float(acct.buying_power),
            'portfolio_value': float(acct.portfolio_value),
            'last_equity': float(acct.last_equity),
            'daily_pnl': float(acct.equity) - float(acct.last_equity),
            'daily_pnl_pct': (float(acct.equity) / float(acct.last_equity) - 1) * 100
                             if float(acct.last_equity) > 0 else 0,
            'status': acct.status,
            'trading_blocked': acct.trading_blocked,
            'paper': self.paper,
        }

    # ── Positions ────────────────────────────────────────────────────────────

    def get_positions(self) -> dict:
        """
        Get all current positions.
        Returns dict of {ticker: {qty, market_value, avg_entry, current_price, pnl, pnl_pct}}.
        """
        positions = self.client.get_all_positions()
        result = {}
        for pos in positions:
            result[pos.symbol] = {
                'qty': float(pos.qty),
                'market_value': float(pos.market_value),
                'avg_entry': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'pnl': float(pos.unrealized_pl),
                'pnl_pct': float(pos.unrealized_plpc) * 100,
                'side': pos.side.value,
            }
        return result

    def get_position(self, ticker: str) -> Optional[dict]:
        """Get position for a single ticker, or None if not held."""
        try:
            pos = self.client.get_open_position(ticker)
            return {
                'qty': float(pos.qty),
                'market_value': float(pos.market_value),
                'avg_entry': float(pos.avg_entry_price),
                'current_price': float(pos.current_price),
                'pnl': float(pos.unrealized_pl),
                'pnl_pct': float(pos.unrealized_plpc) * 100,
            }
        except APIError:
            return None

    # ── Orders ───────────────────────────────────────────────────────────────

    def submit_order(self, ticker: str, notional: float = None,
                     qty: float = None, side: str = 'buy') -> dict:
        """
        Submit a market order.

        Args:
            ticker: Stock symbol (e.g., 'AAPL')
            notional: Dollar amount to buy/sell (fractional shares)
            qty: Number of shares (if notional not specified)
            side: 'buy' or 'sell'

        Returns:
            Order confirmation dict
        """
        if ticker in NON_TRADABLE:
            log.warning(f"  ⚠ {ticker} is not tradable on Alpaca (Canadian ETF). Skipping.")
            return {'status': 'skipped', 'reason': 'non_tradable', 'ticker': ticker}

        order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL

        # Build order kwargs — alpaca-py validates qty/notional at construction
        order_kwargs = {
            'symbol': ticker,
            'time_in_force': TimeInForce.DAY,
            'side': order_side,
        }

        if notional is not None and notional > 0:
            order_kwargs['notional'] = round(notional, 2)
        elif qty is not None and qty > 0:
            order_kwargs['qty'] = qty
        else:
            log.warning(f"  ⚠ {ticker}: No valid notional or qty. Skipping.")
            return {'status': 'skipped', 'reason': 'zero_size', 'ticker': ticker}

        order_data = MarketOrderRequest(**order_kwargs)

        try:
            order = self.client.submit_order(order_data)
            log.info(f"  ✅ {side.upper()} {ticker}: "
                     f"{'$' + str(round(notional, 2)) if notional else str(qty) + ' shares'} "
                     f"→ order {order.id}")
            return {
                'status': 'submitted',
                'order_id': str(order.id),
                'ticker': ticker,
                'side': side,
                'notional': notional,
                'qty': qty,
                'submitted_at': str(order.submitted_at),
            }
        except APIError as e:
            log.error(f"  ❌ Order failed for {ticker}: {e}")
            return {
                'status': 'error',
                'ticker': ticker,
                'error': str(e),
            }

    def close_position(self, ticker: str) -> dict:
        """Close an entire position for a ticker."""
        try:
            self.client.close_position(ticker)
            log.info(f"  🔴 Closed position: {ticker}")
            return {'status': 'closed', 'ticker': ticker}
        except APIError as e:
            log.error(f"  ❌ Failed to close {ticker}: {e}")
            return {'status': 'error', 'ticker': ticker, 'error': str(e)}

    def close_all_positions(self) -> list:
        """Emergency: close all positions."""
        log.warning("⚠️  CLOSING ALL POSITIONS")
        try:
            self.client.close_all_positions(cancel_orders=True)
            log.info("All positions closed.")
            return [{'status': 'all_closed'}]
        except APIError as e:
            log.error(f"❌ Failed to close all: {e}")
            return [{'status': 'error', 'error': str(e)}]

    # ── Order History ────────────────────────────────────────────────────────

    def get_recent_orders(self, limit: int = 20) -> list:
        """Get recent orders."""
        request = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=limit,
        )
        orders = self.client.get_orders(request)
        return [{
            'id': str(o.id),
            'ticker': o.symbol,
            'side': o.side.value,
            'qty': str(o.qty) if o.qty else None,
            'notional': str(o.notional) if o.notional else None,
            'status': o.status.value,
            'filled_avg_price': str(o.filled_avg_price) if o.filled_avg_price else None,
            'submitted_at': str(o.submitted_at),
        } for o in orders]

    # ── Utilities ────────────────────────────────────────────────────────────

    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        clock = self.client.get_clock()
        return clock.is_open
