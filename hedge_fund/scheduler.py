"""
Autonomous Scheduler — runs the hedge fund on autopilot.

Manages both the core portfolio (daily signals at market open) and the
leveraged ETF scanner (intraday scans every 15 minutes).

Uses only stdlib (threading + time) — no external scheduler dependency.

Usage:
    python main.py autopilot              # Live autonomous mode
    python main.py autopilot --dry-run    # Observe without trading
    python main.py autopilot --once       # Run one cycle and exit
"""

import os
import sys
import time
import signal as os_signal
import csv
from datetime import datetime, timedelta
from threading import Event

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from utils.logger import get_logger

log = get_logger('scheduler')

# Timezone handling — Alpaca API gives us market hours in UTC,
# but we schedule based on ET (Eastern Time)
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York')
    UTC = ZoneInfo('UTC')
except ImportError:
    import pytz
    ET = pytz.timezone('America/New_York')
    UTC = pytz.UTC


def now_et() -> datetime:
    """Current time in Eastern."""
    return datetime.now(ET)


def time_str_to_today(time_str: str) -> datetime:
    """Convert 'HH:MM' to a datetime today in ET."""
    h, m = map(int, time_str.split(':'))
    return now_et().replace(hour=h, minute=m, second=0, microsecond=0)


class Autopilot:
    """
    Main autonomous trading daemon.

    Schedule:
        09:25 ET  — Pre-open: refresh data, generate signals
        09:31 ET  — Market open: execute core portfolio trades
        09:31+ ET — Execute leveraged ETF initial positions
        Every 15m — Intraday: scan leveraged ETFs for new signals
        15:55 ET  — Close leveraged ETF day-trades (EOD cleanup)
        16:00 ET  — Market close: generate daily summary

    Safety:
        - Kill switch checked before every trade cycle
        - Leveraged bucket has separate daily loss limit (2%)
        - All trades logged to CSV
        - Graceful shutdown on SIGINT/SIGTERM
    """

    def __init__(self, dry_run: bool = False, once: bool = False):
        self.dry_run = dry_run
        self.once = once
        self.shutdown_event = Event()
        self.scan_interval = config.SCAN_INTERVAL_MINUTES * 60  # seconds
        self.last_scan_time = None
        self.cycle_count = 0
        self.daily_trades = {'core': 0, 'leveraged': 0}

        # Set up signal handlers for graceful shutdown
        os_signal.signal(os_signal.SIGINT, self._handle_shutdown)
        os_signal.signal(os_signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Graceful shutdown handler."""
        log.info("\n⚠️  Shutdown signal received. Finishing current cycle...")
        self.shutdown_event.set()

    def run(self):
        """Main entry point — runs the autonomous loop."""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        log.info(f"""
╔══════════════════════════════════════════════════════════════╗
║   {config.FUND_NAME} — AUTOPILOT [{mode}]
║   Started: {now_et():%Y-%m-%d %H:%M:%S ET}
║
║   Core Portfolio:  ${100_000:>10,.0f}  (17 tickers)
║   Leveraged ETFs:  ${config.LEVERAGED_CAPITAL:>10,.0f}  ({len(config.LEVERAGED_TICKERS)} tickers)
║   Scan interval:   {config.SCAN_INTERVAL_MINUTES} minutes
║
║   Schedule:
║     {config.MARKET_PRE_OPEN_TIME} ET  Pre-open data refresh
║     {config.MARKET_OPEN_TRADE_TIME} ET  Execute core trades
║     Every {config.SCAN_INTERVAL_MINUTES}m   Leveraged ETF scanner
║     {config.MARKET_CLOSE_TIME} ET  Close leveraged positions (EOD)
║
║   Kill Switch: {config.KILL_SWITCH_DD*100:.0f}% drawdown / {config.KILL_SWITCH_DAILY*100:.0f}% daily loss
║   Leveraged Kill: {config.LEVERAGED_DAILY_LOSS_LIMIT*100:.0f}% daily loss on $5K bucket
║
║   Press Ctrl+C for graceful shutdown
╚══════════════════════════════════════════════════════════════╝
""")

        # Ensure log directory exists
        os.makedirs(config.AUTOPILOT_LOG_DIR, exist_ok=True)

        if self.once:
            log.info("Running single cycle (--once mode)...")
            self._run_single_cycle()
            return

        # Main loop
        while not self.shutdown_event.is_set():
            try:
                self._loop_iteration()
            except Exception as e:
                log.error(f"❌ Scheduler error: {e}", exc_info=True)
                # Wait a bit before retrying
                self.shutdown_event.wait(30)

        log.info("\n✅ Autopilot shutdown complete.")

    def _loop_iteration(self):
        """One iteration of the main loop."""
        current = now_et()

        # Check if market is open (or about to be)
        from brokers.alpaca_client import AlpacaClient
        client = AlpacaClient()
        market_open = client.is_market_open()

        if not market_open:
            # Check if we're in pre-market window (9:00-9:30)
            pre_open = time_str_to_today('09:00')
            open_time = time_str_to_today('09:31')

            if pre_open <= current < open_time:
                log.info(f"⏳ Pre-market ({current:%H:%M ET}). "
                         f"Market opens at {config.MARKET_OPEN_TRADE_TIME}. "
                         f"Waiting...")
                self._wait_until(open_time)
                return

            # Market closed — wait until next pre-open
            next_open = self._next_market_open()
            log.info(f"💤 Market closed ({current:%H:%M ET}). "
                     f"Next open: {next_open:%Y-%m-%d %H:%M ET}")
            # Sleep in 60-second intervals (checking shutdown)
            wait_seconds = min((next_open - current).total_seconds(), 3600)
            self.shutdown_event.wait(wait_seconds)
            return

        # Market is open — run the cycle
        self._run_market_cycle(client, current)

    def _run_market_cycle(self, client, current: datetime):
        """Run a single market-hours cycle."""

        # Check if we need to run the open-of-day trades
        open_time = time_str_to_today(config.MARKET_OPEN_TRADE_TIME)
        close_time = time_str_to_today(config.MARKET_CLOSE_TIME)

        today = current.date()

        # Morning trades: run once per day within first 10 minutes of open
        if (self.daily_trades['core'] == 0 and
                open_time <= current <= open_time + timedelta(minutes=10)):
            self._execute_core_trades(client)
            self._execute_leveraged_trades(client)
            self.daily_trades['core'] += 1
            self.daily_trades['leveraged'] += 1
            self.last_scan_time = current

        # EOD: close leveraged positions near market close
        elif current >= close_time:
            self._close_leveraged_eod(client)
            self._log_daily_summary(client)
            # Reset daily counters
            self.daily_trades = {'core': 0, 'leveraged': 0}
            # Wait until next day
            self.shutdown_event.wait(60)
            return

        # Intraday scans
        elif (self.last_scan_time is None or
              (current - self.last_scan_time).total_seconds() >= self.scan_interval):
            self._scan_leveraged(client)
            self.last_scan_time = current

        # Sleep until next check
        self.shutdown_event.wait(30)  # Check every 30 seconds

    def _run_single_cycle(self):
        """Run one complete cycle (for --once mode)."""
        from brokers.alpaca_client import AlpacaClient
        client = AlpacaClient()

        log.info("\n── Core Portfolio Trades ──")
        self._execute_core_trades(client)

        log.info("\n── Leveraged ETF Scan ──")
        self._execute_leveraged_trades(client)

        log.info("\n── Daily Summary ──")
        self._log_daily_summary(client)

    def _execute_core_trades(self, client):
        """Execute the main portfolio trades (same as `python main.py trade`)."""
        log.info(f"\n{'─'*50}")
        log.info(f"  📊 Core Portfolio Trades ({now_et():%H:%M ET})")
        log.info(f"{'─'*50}")

        try:
            from brokers.signal_engine import generate_signals
            from brokers.executor import TradeExecutor

            signal_result = generate_signals()
            executor = TradeExecutor(client, dry_run=self.dry_run)
            result = executor.execute(signal_result)

            if result['status'] == 'halted':
                log.error(f"🛑 Core trading HALTED: {result.get('reason')}")
            else:
                log.info(f"  Core trades: {result['total_orders']} orders "
                         f"{'(DRY RUN)' if self.dry_run else 'executed'}")

            self._log_event('core_trade', result)
            return result

        except Exception as e:
            log.error(f"❌ Core trade error: {e}", exc_info=True)
            self._log_event('core_trade_error', {'error': str(e)})
            return {'status': 'error', 'error': str(e)}

    def _execute_leveraged_trades(self, client):
        """Execute leveraged ETF trades."""
        log.info(f"\n{'─'*50}")
        log.info(f"  ⚡ Leveraged ETF Trades ({now_et():%H:%M ET})")
        log.info(f"{'─'*50}")

        try:
            from brokers.scanner import LeveragedScanner
            scanner = LeveragedScanner()
            result = scanner.execute_scan(client, dry_run=self.dry_run)

            if result.get('status') == 'halted':
                log.error(f"🛑 Leveraged trading HALTED: {result.get('reason')}")
            else:
                total = result.get('total_orders', 0)
                log.info(f"  Leveraged trades: {total} orders "
                         f"{'(DRY RUN)' if self.dry_run else 'executed'}")

            self._log_event('leveraged_trade', result)
            return result

        except Exception as e:
            log.error(f"❌ Leveraged trade error: {e}", exc_info=True)
            self._log_event('leveraged_trade_error', {'error': str(e)})
            return {'status': 'error', 'error': str(e)}

    def _scan_leveraged(self, client):
        """Run an intraday leveraged ETF scan."""
        log.info(f"\n  🔍 Intraday scan ({now_et():%H:%M ET})...")

        try:
            from brokers.scanner import LeveragedScanner
            scanner = LeveragedScanner()
            result = scanner.execute_scan(client, dry_run=self.dry_run)

            total = result.get('total_orders', 0)
            if total > 0:
                log.info(f"  Scan result: {total} trades "
                         f"{'(DRY RUN)' if self.dry_run else 'executed'}")
            else:
                log.info(f"  Scan result: no changes needed")

            self._log_event('intraday_scan', result)

        except Exception as e:
            log.error(f"❌ Scan error: {e}", exc_info=True)

    def _close_leveraged_eod(self, client):
        """Close all leveraged positions at end of day."""
        log.info(f"\n{'─'*50}")
        log.info(f"  🌙 EOD Leveraged Cleanup ({now_et():%H:%M ET})")
        log.info(f"{'─'*50}")

        try:
            from brokers.scanner import LeveragedScanner
            scanner = LeveragedScanner()
            result = scanner.close_all_leveraged(client, dry_run=self.dry_run)
            self._log_event('eod_close', result)

        except Exception as e:
            log.error(f"❌ EOD close error: {e}", exc_info=True)

    def _log_daily_summary(self, client):
        """Generate and log daily summary."""
        log.info(f"\n{'═'*60}")
        log.info(f"  📋 Daily Summary — {now_et():%Y-%m-%d}")
        log.info(f"{'═'*60}")

        try:
            acct = client.get_account()
            positions = client.get_positions()

            # Split positions
            core_positions = {t: p for t, p in positions.items()
                              if t not in config.LEVERAGED_TICKERS}
            lev_positions = {t: p for t, p in positions.items()
                             if t in config.LEVERAGED_TICKERS}

            core_value = sum(p['market_value'] for p in core_positions.values())
            core_pnl = sum(p['pnl'] for p in core_positions.values())
            lev_value = sum(p['market_value'] for p in lev_positions.values())
            lev_pnl = sum(p['pnl'] for p in lev_positions.values())

            log.info(f"\n  Portfolio:    ${acct['portfolio_value']:>12,.2f}")
            log.info(f"  Daily P&L:    ${acct['daily_pnl']:>+12,.2f} "
                     f"({acct['daily_pnl_pct']:+.2f}%)")
            log.info(f"\n  Core:         ${core_value:>12,.2f}  "
                     f"P&L: ${core_pnl:>+10,.2f}  "
                     f"({len(core_positions)} pos)")
            log.info(f"  Leveraged:    ${lev_value:>12,.2f}  "
                     f"P&L: ${lev_pnl:>+10,.2f}  "
                     f"({len(lev_positions)} pos)")
            log.info(f"  Cash:         ${acct['cash']:>12,.2f}")
            log.info(f"{'═'*60}\n")

            self._log_event('daily_summary', {
                'portfolio_value': acct['portfolio_value'],
                'daily_pnl': acct['daily_pnl'],
                'core_value': core_value,
                'core_pnl': core_pnl,
                'lev_value': lev_value,
                'lev_pnl': lev_pnl,
            })

        except Exception as e:
            log.error(f"❌ Summary error: {e}", exc_info=True)

    def _log_event(self, event_type: str, data: dict):
        """Log scheduler event to CSV."""
        log_path = os.path.join(config.AUTOPILOT_LOG_DIR, 'autopilot_log.csv')
        file_exists = os.path.exists(log_path)

        with open(log_path, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'event', 'status', 'details'])
            writer.writerow([
                datetime.now().isoformat(),
                event_type,
                data.get('status', 'ok'),
                str(data)[:500],  # Truncate details
            ])

    def _wait_until(self, target_time: datetime):
        """Wait until a specific time, checking shutdown event."""
        while not self.shutdown_event.is_set():
            now = now_et()
            if now >= target_time:
                return
            remaining = (target_time - now).total_seconds()
            self.shutdown_event.wait(min(remaining, 30))

    def _next_market_open(self) -> datetime:
        """Estimate next market open (9:25 ET next weekday)."""
        current = now_et()
        next_day = current + timedelta(days=1)

        # Skip weekends
        while next_day.weekday() >= 5:  # Saturday=5, Sunday=6
            next_day += timedelta(days=1)

        return next_day.replace(
            hour=9, minute=25, second=0, microsecond=0
        )
