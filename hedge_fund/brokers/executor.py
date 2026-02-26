"""
Trade Executor.

Reconciles target positions vs. current holdings and generates orders.
Includes kill switch, dry-run mode, and trade logging.
"""

import os
import sys
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from utils.logger import get_logger

log = get_logger(__name__)

# Kill switch thresholds
KILL_SWITCH_DD = getattr(config, 'KILL_SWITCH_DD', 0.15)       # 15% drawdown
KILL_SWITCH_DAILY = getattr(config, 'KILL_SWITCH_DAILY', 0.03)  # 3% daily loss
MIN_TRADE_VALUE = getattr(config, 'MIN_TRADE_VALUE', 50)        # $50 minimum


class TradeExecutor:
    """
    Reconciles target portfolio vs. current positions and executes trades.

    Flow:
        1. Get current positions from Alpaca
        2. Get target positions from signal engine
        3. Compute deltas (sells first, then buys)
        4. Execute orders (or log in dry-run mode)
        5. Save trade log
    """

    def __init__(self, alpaca_client, dry_run: bool = False):
        self.client = alpaca_client
        self.dry_run = dry_run
        self.trade_log = []

    def check_kill_switch(self) -> bool:
        """
        Check if portfolio hit kill switch thresholds.
        Returns True if trading should be HALTED.
        """
        try:
            acct = self.client.get_account()
        except Exception as e:
            log.error(f"Kill switch check failed: {e}")
            return True  # Halt on error

        daily_pnl_pct = acct.get('daily_pnl_pct', 0) / 100
        equity = acct.get('equity', 0)
        last_equity = acct.get('last_equity', 0)

        # Daily loss check
        if daily_pnl_pct < -KILL_SWITCH_DAILY:
            log.error(f"🛑 KILL SWITCH: Daily loss {daily_pnl_pct*100:.2f}% "
                      f"exceeds -{KILL_SWITCH_DAILY*100:.0f}% threshold")
            return True

        # Check if account is restricted
        if acct.get('trading_blocked', False):
            log.error("🛑 KILL SWITCH: Trading blocked by Alpaca")
            return True

        return False

    def execute(self, signal_result: dict) -> dict:
        """
        Execute trades to move from current positions to target positions.

        Args:
            signal_result: Output from signal_engine.generate_signals()

        Returns:
            Execution summary dict
        """
        mode = "DRY RUN" if self.dry_run else "LIVE"
        log.info(f"\n{'='*60}")
        log.info(f"  Trade Executor [{mode}]")
        log.info(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
        log.info(f"{'='*60}")

        # ── Kill switch check ────────────────────────────────────────────
        if not self.dry_run and self.check_kill_switch():
            return {
                'status': 'halted',
                'reason': 'kill_switch',
                'timestamp': datetime.now().isoformat(),
            }

        # ── Get account info ─────────────────────────────────────────────
        acct = self.client.get_account()
        portfolio_value = acct['portfolio_value']
        log.info(f"\nAccount equity: ${portfolio_value:,.2f}")
        log.info(f"Buying power:   ${acct['buying_power']:,.2f}")
        log.info(f"Daily P&L:      ${acct['daily_pnl']:+,.2f} "
                 f"({acct['daily_pnl_pct']:+.2f}%)")

        # ── Get current positions ────────────────────────────────────────
        current_positions = self.client.get_positions()
        log.info(f"\nCurrent positions: {len(current_positions)}")
        for t, p in current_positions.items():
            log.info(f"  {t:5s}: ${p['market_value']:>10,.2f}  "
                     f"({p['pnl_pct']:+.1f}%)")

        # ── Compute target positions ─────────────────────────────────────
        from brokers.signal_engine import compute_target_positions
        target_dollars = compute_target_positions(signal_result, portfolio_value)

        log.info(f"\nTarget positions: {sum(1 for v in target_dollars.values() if v > 0)}")
        for t, v in sorted(target_dollars.items(), key=lambda x: -x[1]):
            if v > 0:
                log.info(f"  {t:5s}: ${v:>10,.2f}  "
                         f"({signal_result['target_weights'].get(t,0)*100:.1f}%)")

        # ── Compute deltas ───────────────────────────────────────────────
        sells = []
        buys = []

        # Positions to sell/reduce (currently held but target is 0 or lower)
        for ticker, pos in current_positions.items():
            target = target_dollars.get(ticker, 0)
            current = pos['market_value']
            delta = target - current

            if delta < -MIN_TRADE_VALUE:
                if target < MIN_TRADE_VALUE:
                    # Close entirely
                    sells.append({
                        'ticker': ticker,
                        'action': 'close',
                        'delta': -current,
                    })
                else:
                    # Reduce position
                    sells.append({
                        'ticker': ticker,
                        'action': 'reduce',
                        'delta': delta,
                        'notional': abs(delta),
                    })

        # Positions to buy/increase
        for ticker, target in target_dollars.items():
            if target < MIN_TRADE_VALUE:
                continue
            current = current_positions.get(ticker, {}).get('market_value', 0)
            delta = target - current

            if delta > MIN_TRADE_VALUE:
                buys.append({
                    'ticker': ticker,
                    'action': 'buy' if current == 0 else 'increase',
                    'delta': delta,
                    'notional': delta,
                })

        log.info(f"\nOrder plan: {len(sells)} sells, {len(buys)} buys")

        # ── Execute sells first (free up cash) ───────────────────────────
        results = {'sells': [], 'buys': [], 'skipped': []}

        for order in sells:
            ticker = order['ticker']
            if self.dry_run:
                log.info(f"  [DRY] SELL {ticker}: "
                         f"${abs(order['delta']):,.2f} "
                         f"({order['action']})")
                results['sells'].append({**order, 'status': 'dry_run'})
            else:
                if order['action'] == 'close':
                    result = self.client.close_position(ticker)
                else:
                    result = self.client.submit_order(
                        ticker, notional=order['notional'], side='sell')
                results['sells'].append({**order, **result})

            self._log_trade(order, 'sell')

        # ── Execute buys ─────────────────────────────────────────────────
        for order in buys:
            ticker = order['ticker']
            if self.dry_run:
                log.info(f"  [DRY] BUY  {ticker}: "
                         f"${order['notional']:,.2f} "
                         f"({order['action']})")
                results['buys'].append({**order, 'status': 'dry_run'})
            else:
                result = self.client.submit_order(
                    ticker, notional=order['notional'], side='buy')
                results['buys'].append({**order, **result})

            self._log_trade(order, 'buy')

        # ── Summary ──────────────────────────────────────────────────────
        total_orders = len(sells) + len(buys)
        log.info(f"\n{'='*60}")
        log.info(f"  Execution complete: {total_orders} orders "
                 f"{'(DRY RUN)' if self.dry_run else ''}")
        log.info(f"  Invested: {signal_result['invested_pct']:.1f}%")
        log.info(f"{'='*60}")

        # Save trade log
        self._save_trade_log()

        return {
            'status': 'executed' if not self.dry_run else 'dry_run',
            'total_orders': total_orders,
            'sells': len(sells),
            'buys': len(buys),
            'portfolio_value': portfolio_value,
            'invested_pct': signal_result['invested_pct'],
            'results': results,
            'timestamp': datetime.now().isoformat(),
        }

    def _log_trade(self, order: dict, side: str):
        """Add trade to internal log."""
        self.trade_log.append({
            'timestamp': datetime.now().isoformat(),
            'ticker': order['ticker'],
            'side': side,
            'action': order['action'],
            'delta': order.get('delta', 0),
            'notional': order.get('notional', 0),
            'dry_run': self.dry_run,
        })

    def _save_trade_log(self):
        """Append trade log to CSV file."""
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'reports'
        )
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, 'trade_log.csv')

        file_exists = os.path.exists(log_path)

        with open(log_path, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'ticker', 'side', 'action',
                'delta', 'notional', 'dry_run'
            ])
            if not file_exists:
                writer.writeheader()
            for row in self.trade_log:
                writer.writerow(row)

        if self.trade_log:
            log.info(f"Trade log saved to: {log_path}")


def print_status(client):
    """Print a formatted account & positions dashboard."""
    acct = client.get_account()
    positions = client.get_positions()

    mode = "PAPER" if acct['paper'] else "LIVE"
    print(f"\n{'='*60}")
    print(f"  {config.FUND_NAME} — Account Status [{mode}]")
    print(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'='*60}")
    print(f"  Portfolio Value:  ${acct['portfolio_value']:>12,.2f}")
    print(f"  Cash:             ${acct['cash']:>12,.2f}")
    print(f"  Buying Power:     ${acct['buying_power']:>12,.2f}")
    print(f"  Daily P&L:        ${acct['daily_pnl']:>+12,.2f} "
          f"({acct['daily_pnl_pct']:+.2f}%)")
    print(f"  Market Open:      {'Yes ✅' if client.is_market_open() else 'No ⏸'}")
    print(f"{'='*60}")

    if positions:
        print(f"\n  {'Ticker':<7} {'Value':>10} {'P&L':>10} {'P&L%':>8} {'Qty':>8}")
        print(f"  {'─'*7} {'─'*10} {'─'*10} {'─'*8} {'─'*8}")
        total_val = 0
        total_pnl = 0
        for t in sorted(positions.keys()):
            p = positions[t]
            total_val += p['market_value']
            total_pnl += p['pnl']
            pnl_sign = '+' if p['pnl'] >= 0 else ''
            print(f"  {t:<7} ${p['market_value']:>9,.2f} "
                  f"${pnl_sign}{p['pnl']:>8,.2f} "
                  f"{p['pnl_pct']:>+7.1f}% "
                  f"{p['qty']:>7.2f}")
        print(f"  {'─'*7} {'─'*10} {'─'*10}")
        pnl_sign = '+' if total_pnl >= 0 else ''
        print(f"  {'TOTAL':<7} ${total_val:>9,.2f} "
              f"${pnl_sign}{total_pnl:>8,.2f}")
        cash = acct['portfolio_value'] - total_val
        cash_pct = cash / acct['portfolio_value'] * 100 if acct['portfolio_value'] > 0 else 0
        print(f"  {'CASH':<7} ${cash:>9,.2f} ({cash_pct:.1f}%)")
    else:
        print("\n  No positions held.")

    print()
