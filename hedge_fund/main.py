"""
Mini Hedge Fund — CLI Entry Point

Usage:
    python main.py backtest                  # Full backtest, all tickers
    python main.py backtest --ticker NVDA    # Single ticker
    python main.py walk-forward              # Walk-forward validation
    python main.py report                    # Generate HTML report
    python main.py proposal                  # Generate investor proposal PDF
    python main.py trade                     # Execute paper trades
    python main.py scan                      # Scan leveraged ETFs
    python main.py autopilot                 # Start autonomous scheduler
    python main.py autopilot --dry-run       # Observe without trading
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from utils.logger import get_logger

log = get_logger('main')


def cmd_backtest(args):
    """Run the backtester."""
    from backtester.engine import BacktestEngine

    tickers = config.ALL_TICKERS
    if args.ticker:
        tickers = [args.ticker]
    elif args.sleeve:
        sleeve_map = {
            'etf': config.SLEEVES['ETF'],
            'tech': config.SLEEVES['TECH'],
            'financial': config.SLEEVES['FINANCIAL'],
            'energy': config.SLEEVES['ENERGY'],
            'consumer': config.SLEEVES['CONSUMER'],
        }
        tickers = sleeve_map.get(args.sleeve.lower(), config.ALL_TICKERS)

    engine = BacktestEngine(
        tickers=tickers,
        start=args.start or config.BACKTEST_START,
        end=args.end or config.BACKTEST_END,
        capital=args.capital or config.STARTING_CAPITAL,
    )

    results = engine.run()

    # Save results for reporting
    import pickle
    os.makedirs('reports', exist_ok=True)
    with open('reports/last_backtest.pkl', 'wb') as f:
        pickle.dump(results, f)

    log.info("\nResults saved to reports/last_backtest.pkl")
    return results


def cmd_walk_forward(args):
    """Run walk-forward validation."""
    import pickle
    from backtester.walk_forward import walk_forward_validate

    results_file = 'reports/last_backtest.pkl'
    if os.path.exists(results_file):
        with open(results_file, 'rb') as f:
            results = pickle.load(f)
    else:
        log.info("No backtest results found. Running backtest first...")
        results = cmd_backtest(args)

    wf_results = walk_forward_validate(results['equity_curve'])
    return wf_results


def cmd_report(args):
    """Generate HTML report."""
    import pickle

    results_file = 'reports/last_backtest.pkl'
    if not os.path.exists(results_file):
        log.info("No backtest results found. Running backtest first...")
        results = cmd_backtest(args)
    else:
        with open(results_file, 'rb') as f:
            results = pickle.load(f)

    from reporting.report_generator import generate_report
    report_path = generate_report(results)
    log.info(f"\nReport generated: {report_path}")


def cmd_proposal(args):
    """Generate investor proposal PDF."""
    import pickle

    results_file = 'reports/last_backtest.pkl'
    if not os.path.exists(results_file):
        log.info("No backtest results found. Running backtest first...")
        results = cmd_backtest(args)
    else:
        with open(results_file, 'rb') as f:
            results = pickle.load(f)

    from reporting.fund_tearsheet import generate_proposal
    proposal_path = generate_proposal(results)
    log.info(f"\nProposal generated: {proposal_path}")


def cmd_strategy_doc(args):
    """Generate corporate strategy document PDF."""
    import pickle

    results_file = 'reports/last_backtest.pkl'
    if not os.path.exists(results_file):
        log.info("No backtest results found. Running backtest first...")
        results = cmd_backtest(args)
    else:
        with open(results_file, 'rb') as f:
            results = pickle.load(f)

    from reporting.corporate_report import generate_corporate_report
    doc_path = generate_corporate_report(results)
    log.info(f"\nStrategy document generated: {doc_path}")


def cmd_tech_report(args):
    """Generate technical report PDF."""
    import pickle

    results_file = 'reports/last_backtest.pkl'
    if not os.path.exists(results_file):
        log.info("No backtest results found. Running backtest first...")
        results = cmd_backtest(args)
    else:
        with open(results_file, 'rb') as f:
            results = pickle.load(f)

    from reporting.technical_report import generate_technical_report
    doc_path = generate_technical_report(results)
    log.info(f"\nTechnical report generated: {doc_path}")


def cmd_trade(args):
    """Generate signals and execute paper trades via Alpaca."""
    from brokers.alpaca_client import AlpacaClient
    from brokers.signal_engine import generate_signals
    from brokers.executor import TradeExecutor

    client = AlpacaClient()

    # Generate live signals
    signal_result = generate_signals()

    # Execute (or dry-run)
    executor = TradeExecutor(client, dry_run=args.dry_run)
    result = executor.execute(signal_result)

    if result['status'] == 'halted':
        log.error(f"Trading HALTED: {result.get('reason', 'unknown')}")
    elif result['status'] == 'dry_run':
        log.info(f"\nDry run complete. {result['total_orders']} orders would be placed.")
        log.info("Run without --dry-run to execute.")
    else:
        log.info(f"\n{result['total_orders']} orders executed.")


def cmd_status(args):
    """Show Alpaca account status and positions."""
    from brokers.alpaca_client import AlpacaClient
    from brokers.executor import print_status

    client = AlpacaClient()
    print_status(client)


def cmd_scan(args):
    """Run one leveraged ETF scan cycle."""
    from brokers.alpaca_client import AlpacaClient
    from brokers.scanner import LeveragedScanner

    client = AlpacaClient()
    scanner = LeveragedScanner()
    result = scanner.execute_scan(client, dry_run=args.dry_run)

    if result.get('status') == 'halted':
        log.error(f"Leveraged trading HALTED: {result.get('reason')}")
    elif result.get('status') == 'dry_run':
        log.info(f"\nDry run complete. {result.get('total_orders', 0)} orders would be placed.")
    else:
        log.info(f"\n{result.get('total_orders', 0)} leveraged orders executed.")


def cmd_autopilot(args):
    """Start the autonomous trading scheduler."""
    from scheduler import Autopilot

    autopilot = Autopilot(
        dry_run=args.dry_run,
        once=args.once,
    )
    autopilot.run()


def cmd_dashboard(args):
    """Show live signals, targets, and positions side-by-side."""
    from brokers.alpaca_client import AlpacaClient
    from brokers.signal_engine import generate_signals, compute_target_positions
    from brokers.executor import print_status

    client = AlpacaClient()

    # Show account status
    print_status(client)

    # Generate signals
    signal_result = generate_signals()
    acct = client.get_account()
    targets = compute_target_positions(signal_result, acct['portfolio_value'])

    # Signal summary
    print(f"\n{'='*60}")
    print(f"  Live Signal Dashboard")
    print(f"{'='*60}")
    print(f"  {'Ticker':<7} {'Signal':<8} {'Strategy':<22} {'Target $':>10} {'Weight':>8}")
    print(f"  {'─'*7} {'─'*8} {'─'*22} {'─'*10} {'─'*8}")

    for t, detail in sorted(signal_result['signal_details'].items(),
                            key=lambda x: -signal_result['target_weights'].get(x[0], 0)):
        sig = "🟢 LONG" if detail['signal'] == 1 else "⚪ FLAT"
        tgt = targets.get(t, 0)
        wt = signal_result['target_weights'].get(t, 0) * 100
        print(f"  {t:<7} {sig:<8} {detail['strategy']:<22} "
              f"${tgt:>9,.2f} {wt:>7.1f}%")

    print(f"\n  Invested: {signal_result['invested_pct']:.1f}% | "
          f"Cash: {100 - signal_result['invested_pct']:.1f}%")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Mini Hedge Fund — Algorithmic Trading System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python main.py backtest
  python main.py backtest --ticker NVDA
  python main.py backtest --sleeve tech
  python main.py walk-forward
  python main.py report
  python main.py proposal
  python main.py strategy-doc
  python main.py tech-report
  python main.py trade --dry-run
  python main.py trade
  python main.py status
  python main.py dashboard
        '''
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Backtest
    bt = subparsers.add_parser('backtest', help='Run backtest')
    bt.add_argument('--ticker', type=str, help='Single ticker to backtest')
    bt.add_argument('--sleeve', type=str, help='Sleeve to backtest (etf/tech/financial/energy/consumer)')
    bt.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    bt.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    bt.add_argument('--capital', type=float, help='Starting capital')

    # Walk-forward
    wf = subparsers.add_parser('walk-forward', help='Walk-forward validation')
    wf.add_argument('--start', type=str, default=None)
    wf.add_argument('--end', type=str, default=None)
    wf.add_argument('--capital', type=float, default=None)
    wf.add_argument('--ticker', type=str, default=None)
    wf.add_argument('--sleeve', type=str, default=None)

    # Report
    rpt = subparsers.add_parser('report', help='Generate HTML report')
    rpt.add_argument('--start', type=str, default=None)
    rpt.add_argument('--end', type=str, default=None)
    rpt.add_argument('--capital', type=float, default=None)
    rpt.add_argument('--ticker', type=str, default=None)
    rpt.add_argument('--sleeve', type=str, default=None)

    # Proposal
    prop = subparsers.add_parser('proposal', help='Generate investor proposal PDF')
    prop.add_argument('--start', type=str, default=None)
    prop.add_argument('--end', type=str, default=None)
    prop.add_argument('--capital', type=float, default=None)
    prop.add_argument('--ticker', type=str, default=None)
    prop.add_argument('--sleeve', type=str, default=None)

    # Trade (Alpaca)
    tr = subparsers.add_parser('trade', help='Execute paper trades via Alpaca')
    tr.add_argument('--dry-run', action='store_true',
                    help='Show what would trade, without executing')

    # Scan (leveraged ETFs)
    sc = subparsers.add_parser('scan', help='Scan leveraged ETFs for opportunities')
    sc.add_argument('--dry-run', action='store_true',
                    help='Show signals without executing trades')

    # Autopilot
    ap = subparsers.add_parser('autopilot', help='Start autonomous trading scheduler')
    ap.add_argument('--dry-run', action='store_true',
                    help='Run scheduler without executing trades')
    ap.add_argument('--once', action='store_true',
                    help='Run one cycle and exit')

    # Status
    subparsers.add_parser('status', help='Show Alpaca account & positions')

    # Strategy Document
    subparsers.add_parser('strategy-doc', help='Generate corporate strategy document PDF')

    # Technical Report
    subparsers.add_parser('tech-report', help='Generate technical report PDF')

    # Dashboard
    subparsers.add_parser('dashboard', help='Live signals + positions dashboard')

    args = parser.parse_args()

    if args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'walk-forward':
        cmd_walk_forward(args)
    elif args.command == 'report':
        cmd_report(args)
    elif args.command == 'proposal':
        cmd_proposal(args)
    elif args.command == 'strategy-doc':
        cmd_strategy_doc(args)
    elif args.command == 'tech-report':
        cmd_tech_report(args)
    elif args.command == 'trade':
        cmd_trade(args)
    elif args.command == 'scan':
        cmd_scan(args)
    elif args.command == 'autopilot':
        cmd_autopilot(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'dashboard':
        cmd_dashboard(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

