"""
Intraday Scanner — Leveraged ETF Opportunity Scanner.

Runs every N minutes during market hours, scanning leveraged ETFs
for momentum signals and executing trades against a ring-fenced $5K allocation.
"""

import os
import sys
from datetime import datetime

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from data.fetcher import fetch_single
from data.processor import add_indicators
from strategies.registry import get_strategy_for_ticker
from utils.logger import get_logger

log = get_logger(__name__)


class LeveragedScanner:
    """
    Scans leveraged ETFs and manages the $5K ring-fenced allocation.

    Flow:
        1. Fetch latest data for leveraged ETF universe
        2. Run leveraged_momentum strategy on each
        3. Compute target positions within $5K budget
        4. Return trade instructions
    """

    def __init__(self, capital: float = None, max_per_position: float = None):
        self.capital = capital or config.LEVERAGED_CAPITAL
        self.max_per_position = max_per_position or config.LEVERAGED_MAX_PER_POSITION
        self.tickers = config.LEVERAGED_TICKERS
        self.daily_loss_limit = config.LEVERAGED_DAILY_LOSS_LIMIT
        self.start_of_day_value = self.capital  # Reset each trading day

    def scan(self, lookback_days: int = 100) -> dict:
        """
        Run one scan cycle.

        Returns:
            dict with signals, targets, and trade instructions
        """
        end = datetime.now().strftime('%Y-%m-%d')
        start = pd.Timestamp(end) - pd.Timedelta(days=lookback_days)
        start = start.strftime('%Y-%m-%d')

        log.info(f"🔍 Scanning {len(self.tickers)} leveraged ETFs...")

        # Fetch data
        data = {}
        for ticker in self.tickers:
            try:
                df = fetch_single(ticker, start, end)
                if df is not None and len(df) > 20:
                    data[ticker] = add_indicators(df)
                else:
                    log.warning(f"  {ticker}: Insufficient data")
            except Exception as e:
                log.warning(f"  {ticker}: Fetch failed — {e}")

        if not data:
            log.warning("No data available for leveraged ETFs")
            return {'signals': {}, 'targets': {}, 'status': 'no_data'}

        # Generate signals
        signals = {}
        signal_details = {}

        for ticker in data:
            strategy = get_strategy_for_ticker(ticker)
            sig_series = strategy.generate_signals(data[ticker])
            current_signal = int(sig_series.iloc[-1]) if len(sig_series) > 0 else 0
            signals[ticker] = current_signal

            # Recent activation
            recent = sig_series.tail(21)
            activation = recent.mean() * 100 if len(recent) > 0 else 0

            signal_details[ticker] = {
                'signal': current_signal,
                'strategy': 'leveraged_momentum',
                'activation_pct': round(activation, 1),
                'last_price': round(float(data[ticker]['Close'].iloc[-1]), 2),
            }

            status = "🟢 LONG" if current_signal == 1 else "⚪ FLAT"
            log.info(f"  {ticker:5s} → {status}  (activation: {activation:.0f}%)")

        # Compute target positions within $5K budget
        active = [t for t, s in signals.items() if s == 1]
        targets = {}

        if active:
            per_position = min(
                self.capital / len(active),
                self.max_per_position
            )
            for ticker in active:
                targets[ticker] = round(per_position, 2)

        total_allocated = sum(targets.values())
        cash = self.capital - total_allocated

        log.info(f"\n  Leveraged allocation: ${total_allocated:,.2f} / "
                 f"${self.capital:,.2f}  ({len(active)}/{len(self.tickers)} active)")
        log.info(f"  Leveraged cash: ${cash:,.2f}")

        return {
            'signals': signals,
            'signal_details': signal_details,
            'targets': targets,
            'active_count': len(active),
            'total_count': len(self.tickers),
            'allocated': total_allocated,
            'cash': cash,
            'capital': self.capital,
            'timestamp': datetime.now().isoformat(),
        }

    def execute_scan(self, client, dry_run: bool = False) -> dict:
        """
        Full scan + execute cycle.

        Args:
            client: AlpacaClient instance
            dry_run: If True, show trades without executing

        Returns:
            Execution result dict
        """
        scan_result = self.scan()

        if scan_result.get('status') == 'no_data':
            return scan_result

        # Get current leveraged positions
        all_positions = client.get_positions()
        lev_positions = {t: p for t, p in all_positions.items()
                         if t in self.tickers}

        # Check daily loss limit
        current_lev_value = sum(p['market_value'] for p in lev_positions.values())
        lev_pnl = sum(p['pnl'] for p in lev_positions.values())
        if current_lev_value > 0:
            daily_loss_pct = lev_pnl / self.capital
            if daily_loss_pct < -self.daily_loss_limit:
                log.error(f"🛑 Leveraged KILL SWITCH: Daily loss "
                          f"{daily_loss_pct*100:.1f}% exceeds "
                          f"-{self.daily_loss_limit*100:.0f}% limit. "
                          f"Closing all leveraged positions.")
                if not dry_run:
                    for ticker in lev_positions:
                        client.close_position(ticker)
                return {
                    'status': 'halted',
                    'reason': 'leveraged_daily_loss_limit',
                    'pnl_pct': daily_loss_pct,
                }

        # Compute deltas
        sells = []
        buys = []
        min_trade = 25  # $25 minimum for leveraged trades

        # Positions to close (held but not in targets)
        for ticker, pos in lev_positions.items():
            target = scan_result['targets'].get(ticker, 0)
            if target < min_trade:
                sells.append({
                    'ticker': ticker,
                    'action': 'close',
                    'current': pos['market_value'],
                })

        # Positions to open/increase
        for ticker, target in scan_result['targets'].items():
            current = lev_positions.get(ticker, {}).get('market_value', 0)
            delta = target - current
            if delta > min_trade:
                buys.append({
                    'ticker': ticker,
                    'action': 'buy' if current == 0 else 'increase',
                    'notional': delta,
                })

        mode = "DRY RUN" if dry_run else "LIVE"
        log.info(f"\n  Scanner [{mode}]: {len(sells)} sells, {len(buys)} buys")

        results = {'sells': [], 'buys': []}

        # Execute sells first
        for order in sells:
            if dry_run:
                log.info(f"  [DRY] SELL {order['ticker']}: "
                         f"${order['current']:,.2f} (close)")
                results['sells'].append({**order, 'status': 'dry_run'})
            else:
                result = client.close_position(order['ticker'])
                results['sells'].append({**order, **result})

        # Execute buys
        for order in buys:
            if dry_run:
                log.info(f"  [DRY] BUY  {order['ticker']}: "
                         f"${order['notional']:,.2f}")
                results['buys'].append({**order, 'status': 'dry_run'})
            else:
                result = client.submit_order(
                    order['ticker'], notional=order['notional'], side='buy')
                results['buys'].append({**order, **result})

        total_orders = len(sells) + len(buys)
        log.info(f"  Scanner complete: {total_orders} orders "
                 f"{'(DRY RUN)' if dry_run else ''}")

        return {
            'status': 'executed' if not dry_run else 'dry_run',
            'total_orders': total_orders,
            'sells': len(sells),
            'buys': len(buys),
            'scan': scan_result,
            'results': results,
            'timestamp': datetime.now().isoformat(),
        }

    def close_all_leveraged(self, client, dry_run: bool = False) -> dict:
        """Close all leveraged ETF positions (end-of-day cleanup)."""
        all_positions = client.get_positions()
        lev_positions = {t: p for t, p in all_positions.items()
                         if t in self.tickers}

        if not lev_positions:
            log.info("  No leveraged positions to close.")
            return {'status': 'no_positions'}

        log.info(f"  Closing {len(lev_positions)} leveraged positions "
                 f"(EOD cleanup)...")

        results = []
        for ticker, pos in lev_positions.items():
            if dry_run:
                log.info(f"  [DRY] CLOSE {ticker}: ${pos['market_value']:,.2f}")
                results.append({'ticker': ticker, 'status': 'dry_run'})
            else:
                result = client.close_position(ticker)
                results.append(result)

        return {
            'status': 'closed' if not dry_run else 'dry_run',
            'count': len(lev_positions),
            'results': results,
        }
