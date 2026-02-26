"""
Configuration for the Mini Hedge Fund trading system.
All parameters, universe definitions, and strategy defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Universe ──────────────────────────────────────────────────────────────────

UNIVERSE = {
    'etf': {
        'broad':    ['VOO', 'QQQ'],
        'income':   ['SCHD'],
        'sector':   ['FTXL', 'XLE', 'ZEB'],
        'emerging': ['SPEM', 'EWZ', 'EWY'],
    },
    'stocks': {
        'tech':       ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'ASML'],
        'financials': ['JPM', 'GS', 'BAC'],
        'energy':     ['XOM', 'CVX'],
        'consumer':   ['AMZN', 'TSLA'],
        'semiconductor': ['SNDK', 'AXTI'],
    }
}

ALL_TICKERS = [t for sleeve in UNIVERSE.values()
               for group in sleeve.values()
               for t in group]

BENCHMARK = 'VOO'

# ── Ticker Aliases (for yfinance) ─────────────────────────────────────────────

TICKER_ALIASES = {
    'ZEB': 'ZEB.TO',  # Canadian ETF listed on TSX
}

# ── Sleeve Definitions (for allocation constraints) ──────────────────────────

SLEEVES = {
    'ETF':           ['VOO', 'FTXL', 'QQQ', 'SCHD', 'SPEM', 'ZEB', 'XLE', 'EWZ', 'EWY'],
    'TECH':          ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'ASML'],
    'FINANCIAL':     ['JPM', 'GS', 'BAC'],
    'ENERGY':        ['XOM', 'CVX'],
    'CONSUMER':      ['AMZN', 'TSLA'],
    'SEMICONDUCTOR': ['SNDK', 'AXTI'],
}

# ── Portfolio Allocation Ratios ──────────────────────────────────────────────
#    70% ETFs & index funds, 20% individual stocks, 10% leveraged ETFs

ETF_TICKERS = ['VOO', 'QQQ', 'SCHD', 'FTXL', 'XLE', 'SPEM', 'EWZ', 'EWY']
STOCK_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'JPM', 'GS', 'BAC',
                 'XOM', 'CVX', 'AMZN', 'TSLA', 'SNDK', 'AXTI', 'ASML']

PORTFOLIO_ALLOCATION = {
    'etf':       0.70,   # 70% of portfolio
    'stocks':    0.20,   # 20% of portfolio
    'leveraged': 0.10,   # 10% of portfolio
}

# Reverse lookup: ticker → sleeve name
TICKER_TO_SLEEVE = {}
for sleeve_name, tickers in SLEEVES.items():
    for t in tickers:
        TICKER_TO_SLEEVE[t] = sleeve_name

# ── Strategy Assignments (from PDF analysis) ──────────────────────────────────

STRATEGY_ASSIGNMENTS = {
    # Aggressive Momentum (fast EMA + MACD)
    'VOO':   'aggressive_momentum',
    'QQQ':   'aggressive_momentum',
    'AAPL':  'aggressive_momentum',
    'MSFT':  'aggressive_momentum',
    'NVDA':  'aggressive_momentum',
    'GOOGL': 'aggressive_momentum',
    'AMZN':  'aggressive_momentum',
    'TSLA':  'aggressive_momentum',
    'ASML':  'aggressive_momentum',
    'SNDK':  'aggressive_momentum',
    'AXTI':   'aggressive_momentum',

    # Dual Momentum (absolute + relative momentum)
    'SCHD':  'dual_momentum',
    'SPEM':  'dual_momentum',
    'EWZ':   'dual_momentum',
    'EWY':   'dual_momentum',
    'JPM':   'dual_momentum',
    'GS':    'dual_momentum',
    'BAC':   'dual_momentum',
    'XOM':   'dual_momentum',
    'CVX':   'dual_momentum',

    # Sector Momentum Rotation (kept, but with more aggressive params)
    'FTXL':  'sector_momentum',
    'ZEB':   'sector_momentum',
    'XLE':   'sector_momentum',
}

# ── Allocation Constraints ────────────────────────────────────────────────────

MAX_TICKER_WEIGHT = 0.15    # No single ticker > 15%
MAX_SLEEVE_WEIGHT = 0.35    # No single sleeve > 35%
MIN_TICKER_WEIGHT = 0.01    # Drop tickers below 1%
REBALANCE_FREQ = 'monthly'
VOL_LOOKBACK_DAYS = 60

# ── Backtest ──────────────────────────────────────────────────────────────────

BACKTEST_START = '2020-01-01'
BACKTEST_END = '2025-12-31'
STARTING_CAPITAL = 10_000
SLIPPAGE = 0.001         # 10 bps
COMMISSION = 1.00        # $1 per trade

# ── SMA Momentum Defaults (PDF §3.12, Eq. 322-323) ──────────────────────────

SMA_FAST = 50
SMA_SLOW = 200
SMA_STOP_LOSS = 0.08          # 8% default
SMA_STOP_LOSS_HIGH_VOL = 0.10  # 10% for NVDA, TSLA

HIGH_VOL_TICKERS = ['NVDA', 'TSLA']

# ── Mean Reversion Defaults (PDF §3.9-3.10, §10.3) ──────────────────────────

MR_LOOKBACK = 20
MR_ENTRY_Z = 2.0
MR_EXIT_Z = 0.5
MR_BOLLINGER = 2.0
MR_MAX_HOLD = 15
MR_ALLOW_SHORT = False
MR_STOP_LOSS = 0.05

# ── Sector Momentum Defaults (PDF §4.1.1) ────────────────────────────────────

SM_LOOKBACK = 63              # ~3 months (was 6 months — too slow)
SM_MA_FILTER = 100            # 100-day MA filter (was 200 — too slow)
SM_TOP_FRACTION = 0.5

# ── Aggressive Momentum Defaults ─────────────────────────────────────────

AGG_EMA_FAST = 12
AGG_EMA_SLOW = 26
AGG_TRAILING_STOP = 0.12
AGG_RSI_EXIT_FLOOR = 30

# ── Dual Momentum Defaults ───────────────────────────────────────────────

DUAL_LOOKBACK = 63            # ~3 months
DUAL_MIN_LOOKBACK = 21        # ~1 month
DUAL_TREND_FILTER = 100       # SMA 100

# ── Allocation Mode ──────────────────────────────────────────────────────

ALLOCATION_MODE = 'momentum'  # 'momentum' or 'inverse_vol'

# ── Brokers ───────────────────────────────────────────────────────────────────

ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
ALPACA_PAPER = True

IBKR_HOST = '127.0.0.1'
IBKR_PORT = 7497
IBKR_CLIENT_ID = 1

# ── Live Trading ──────────────────────────────────────────────────────────────

LIVE_TICKERS = [t for t in ALL_TICKERS if t != 'ZEB']  # ZEB not on Alpaca
MIN_TRADE_VALUE = 50          # Skip trades below $50
KILL_SWITCH_DD = 0.15         # Halt if drawdown exceeds 15%
KILL_SWITCH_DAILY = 0.03      # Halt if daily loss exceeds 3%

# ── Reporting ─────────────────────────────────────────────────────────────────

REPORT_DIR = './reports'
REPORT_TITLE = 'Mini Hedge Fund — Strategy Backtest Report'
FUND_NAME = 'HR Capital'

# ── Leveraged ETF Universe (High Risk / Ring-Fenced) ─────────────────────────

LEVERAGED_TICKERS = ['TQQQ', 'SOXL', 'UPRO', 'SPXL', 'TECL']
LEVERAGED_CAPITAL = 5000               # $5K ring-fenced allocation
LEVERAGED_MAX_PER_POSITION = 2000      # Max $2K per leveraged position
LEVERAGED_MAX_HOLD_DAYS = 5            # Decay protection: max 5 day hold
LEVERAGED_TRAILING_STOP = 0.05         # 5% trailing stop (tight for 3x)
LEVERAGED_DAILY_LOSS_LIMIT = 0.02      # 2% of leveraged capital max daily loss

# Strategy assignments for leveraged tickers
for _lt in LEVERAGED_TICKERS:
    STRATEGY_ASSIGNMENTS[_lt] = 'leveraged_momentum'

# ── Scheduler / Autopilot ────────────────────────────────────────────────────

SCAN_INTERVAL_MINUTES = 15             # Intraday scan frequency
MARKET_OPEN_TRADE_TIME = '09:31'       # Execute core trades at this time (ET)
MARKET_PRE_OPEN_TIME = '09:25'         # Pre-open data refresh (ET)
MARKET_CLOSE_TIME = '15:55'            # Close leveraged day-trades (ET)
AUTOPILOT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
