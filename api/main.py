"""
FastAPI Backend — Hedge Fund Dashboard API.

Bridges the Next.js dashboard frontend to the existing hedge fund engine.
Provides REST endpoints for portfolio data, signals, trades, scanner,
autopilot control, and configuration management.
"""

import os
import sys
import csv
import json
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add hedge_fund to path
HF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'hedge_fund')
sys.path.insert(0, HF_DIR)
os.chdir(HF_DIR)

# Ensure log directory is writable — fallback to /tmp if needed
log_dir = os.path.join(HF_DIR, 'logs')
try:
    os.makedirs(log_dir, exist_ok=True)
    test_file = os.path.join(log_dir, '.write_test')
    with open(test_file, 'w') as f:
        f.write('ok')
    os.remove(test_file)
except (PermissionError, OSError):
    # Fall back to /tmp
    log_dir = '/tmp/hedgefund_logs'
    os.makedirs(log_dir, exist_ok=True)
    os.environ['HF_LOG_DIR'] = log_dir

import config
from brokers.alpaca_client import AlpacaClient
from utils.logger import get_logger

log = get_logger('api')

# ── Globals ──────────────────────────────────────────────────────────────────
client: AlpacaClient = None
autopilot_task: asyncio.Task = None
autopilot_running = False
connected_ws: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Alpaca client on startup."""
    global client
    client = AlpacaClient()
    log.info("API started — Alpaca client initialized")
    yield
    log.info("API shutdown")


app = FastAPI(
    title="HR Capital — Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ══════════════════════════════════════════════════════════════════════════════
class TradeRequest(BaseModel):
    ticker: str
    side: str  # 'buy' or 'sell'
    amount: float  # dollar amount
    dry_run: bool = False


class ConfigUpdate(BaseModel):
    etf_pct: Optional[float] = None
    stock_pct: Optional[float] = None
    leveraged_pct: Optional[float] = None
    kill_switch_dd: Optional[float] = None
    kill_switch_daily: Optional[float] = None
    scan_interval: Optional[int] = None
    leveraged_capital: Optional[float] = None


# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/portfolio")
async def get_portfolio():
    """Live portfolio: account metrics, positions, allocation breakdown."""
    acct = client.get_account()
    positions = client.get_positions()

    # Categorize positions
    etf_positions = []
    stock_positions = []
    leveraged_positions = []
    other_positions = []

    for ticker, pos in sorted(positions.items()):
        entry = {
            'ticker': ticker,
            'market_value': pos['market_value'],
            'pnl': pos['pnl'],
            'pnl_pct': pos['pnl_pct'],
            'qty': pos['qty'],
            'avg_entry': pos.get('avg_entry', 0),
            'current_price': pos.get('current_price', 0),
        }

        if ticker in config.ETF_TICKERS:
            entry['category'] = 'etf'
            etf_positions.append(entry)
        elif ticker in config.STOCK_TICKERS:
            entry['category'] = 'stock'
            stock_positions.append(entry)
        elif ticker in config.LEVERAGED_TICKERS:
            entry['category'] = 'leveraged'
            leveraged_positions.append(entry)
        else:
            entry['category'] = 'other'
            other_positions.append(entry)

    etf_total = sum(p['market_value'] for p in etf_positions)
    stock_total = sum(p['market_value'] for p in stock_positions)
    lev_total = sum(p['market_value'] for p in leveraged_positions)
    total_invested = etf_total + stock_total + lev_total

    return {
        'account': {
            'portfolio_value': acct['portfolio_value'],
            'equity': acct['equity'],
            'cash': acct['cash'],
            'buying_power': acct['buying_power'],
            'daily_pnl': acct['daily_pnl'],
            'daily_pnl_pct': acct['daily_pnl_pct'],
            'market_open': client.is_market_open(),
        },
        'allocation': {
            'etf': {'value': etf_total, 'pct': etf_total / acct['portfolio_value'] * 100 if acct['portfolio_value'] > 0 else 0, 'target_pct': 70, 'count': len(etf_positions)},
            'stocks': {'value': stock_total, 'pct': stock_total / acct['portfolio_value'] * 100 if acct['portfolio_value'] > 0 else 0, 'target_pct': 20, 'count': len(stock_positions)},
            'leveraged': {'value': lev_total, 'pct': lev_total / acct['portfolio_value'] * 100 if acct['portfolio_value'] > 0 else 0, 'target_pct': 10, 'count': len(leveraged_positions)},
            'cash': {'value': acct['cash'], 'pct': acct['cash'] / acct['portfolio_value'] * 100 if acct['portfolio_value'] > 0 else 0},
        },
        'positions': {
            'etf': etf_positions,
            'stocks': stock_positions,
            'leveraged': leveraged_positions,
            'other': other_positions,
        },
        'total_positions': len(positions),
        'total_invested': total_invested,
        'timestamp': datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  PORTFOLIO HISTORY (Equity Curve)
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/portfolio/history")
async def get_portfolio_history(period: str = "1D"):
    """
    Portfolio equity curve from Alpaca's portfolio history API.
    Periods: 1D, 1W, 1M, 3M, 1Y, ALL
    Returns timestamps + equity values for charting.
    """
    import requests as req_lib

    # Map period to Alpaca API params
    period_map = {
        '1D': {'period': '1D', 'timeframe': '5Min'},
        '1W': {'period': '1W', 'timeframe': '15Min'},
        '1M': {'period': '1M', 'timeframe': '1D'},
        '3M': {'period': '3M', 'timeframe': '1D'},
        '1Y': {'period': '1A', 'timeframe': '1D'},
        'ALL': {'period': 'all', 'timeframe': '1D'},
    }

    params = period_map.get(period, period_map['1D'])

    # Direct Alpaca REST API call
    base_url = 'https://paper-api.alpaca.markets' if client.paper else 'https://api.alpaca.markets'
    headers = {
        'APCA-API-KEY-ID': client.api_key,
        'APCA-API-SECRET-KEY': client.secret_key,
    }

    try:
        resp = req_lib.get(
            f'{base_url}/v2/account/portfolio/history',
            headers=headers,
            params={
                'period': params['period'],
                'timeframe': params['timeframe'],
                'extended_hours': 'true',
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        timestamps = data.get('timestamp', [])
        equity = data.get('equity', [])
        profit_loss = data.get('profit_loss', [])
        profit_loss_pct = data.get('profit_loss_pct', [])
        base_value = data.get('base_value', 0)

        # Build chart-friendly data points
        points = []
        for i, ts in enumerate(timestamps):
            points.append({
                'time': ts,
                'equity': equity[i] if i < len(equity) and equity[i] is not None else None,
                'pnl': profit_loss[i] if i < len(profit_loss) and profit_loss[i] is not None else None,
                'pnl_pct': profit_loss_pct[i] if i < len(profit_loss_pct) and profit_loss_pct[i] is not None else None,
            })

        # Filter out None equity values
        points = [p for p in points if p['equity'] is not None]

        # Calculate summary stats
        if points:
            start_val = points[0]['equity']
            end_val = points[-1]['equity']
            high_val = max(p['equity'] for p in points)
            low_val = min(p['equity'] for p in points)
            change = end_val - start_val
            change_pct = (change / start_val * 100) if start_val > 0 else 0
        else:
            start_val = end_val = high_val = low_val = change = change_pct = 0

        return {
            'period': period,
            'timeframe': params['timeframe'],
            'points': points,
            'summary': {
                'start': start_val,
                'end': end_val,
                'high': high_val,
                'low': low_val,
                'change': change,
                'change_pct': change_pct,
                'base_value': base_value,
            },
            'point_count': len(points),
        }

    except Exception as e:
        log.error(f"Portfolio history error: {e}")
        raise HTTPException(500, f"Failed to fetch portfolio history: {str(e)}")


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNALS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/signals")
async def get_signals():
    """Current strategy signals for all tickers."""
    from brokers.signal_engine import generate_signals
    result = generate_signals()
    return {
        'signals': result['signal_details'],
        'target_weights': result['target_weights'],
        'invested_pct': result['invested_pct'],
        'active_count': sum(1 for s in result['signals'].values() if s == 1),
        'total_count': len(result['signals']),
        'failed_tickers': result['failed_tickers'],
        'timestamp': result['timestamp'],
    }


@app.get("/api/signals/leveraged")
async def get_leveraged_signals():
    """Current leveraged ETF scanner signals."""
    from brokers.scanner import LeveragedScanner
    scanner = LeveragedScanner()
    result = scanner.scan()
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  TRADES ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/trades")
async def get_trades():
    """Recent trade history from CSV log."""
    log_path = os.path.join(config.REPORT_DIR, 'trade_log.csv')
    trades = []

    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                trades.append(row)

    return {
        'trades': trades[-50:],  # Last 50 trades
        'total': len(trades),
    }


@app.post("/api/trades/execute")
async def execute_trade(req: TradeRequest):
    """Execute a single trade."""
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    if req.side not in ('buy', 'sell'):
        raise HTTPException(400, "Side must be 'buy' or 'sell'")

    if req.dry_run:
        return {
            'status': 'dry_run',
            'ticker': req.ticker,
            'side': req.side,
            'amount': req.amount,
            'message': f'Would {req.side} ${req.amount:.2f} of {req.ticker}',
        }

    result = client.submit_order(req.ticker, notional=req.amount, side=req.side)
    return result


@app.post("/api/trades/rebalance")
async def trigger_rebalance(dry_run: bool = True):
    """Trigger a full portfolio rebalance."""
    from brokers.signal_engine import generate_signals
    from brokers.executor import TradeExecutor

    signal_result = generate_signals()
    executor = TradeExecutor(client, dry_run=dry_run)
    result = executor.execute(signal_result)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  SCANNER ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/scanner")
async def get_scanner_status():
    """Latest leveraged ETF scan results."""
    from brokers.scanner import LeveragedScanner
    scanner = LeveragedScanner()
    result = scanner.scan()
    return result


@app.post("/api/scanner/run")
async def run_scanner(dry_run: bool = True):
    """Force run one scan cycle."""
    from brokers.scanner import LeveragedScanner
    scanner = LeveragedScanner()
    result = scanner.execute_scan(client, dry_run=dry_run)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOPILOT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/autopilot/status")
async def autopilot_status():
    """Current autopilot scheduler status."""
    # Read last log entries
    log_path = os.path.join(config.AUTOPILOT_LOG_DIR, 'autopilot_log.csv')
    recent_events = []

    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            reader = csv.DictReader(f)
            events = list(reader)
            recent_events = events[-20:]  # Last 20 events

    return {
        'running': autopilot_running,
        'scan_interval': config.SCAN_INTERVAL_MINUTES,
        'market_open_time': config.MARKET_OPEN_TRADE_TIME,
        'market_close_time': config.MARKET_CLOSE_TIME,
        'recent_events': recent_events,
        'market_open': client.is_market_open(),
        'timestamp': datetime.now().isoformat(),
    }


@app.post("/api/autopilot/start")
async def start_autopilot(dry_run: bool = True):
    """Start the autopilot scheduler as a background task."""
    global autopilot_task, autopilot_running

    if autopilot_running:
        return {'status': 'already_running'}

    from scheduler import Autopilot
    pilot = Autopilot(dry_run=dry_run)
    autopilot_running = True

    async def run_pilot():
        global autopilot_running
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, pilot.run)
        finally:
            autopilot_running = False

    autopilot_task = asyncio.create_task(run_pilot())

    return {
        'status': 'started',
        'dry_run': dry_run,
        'message': f'Autopilot started {"(DRY RUN)" if dry_run else "(LIVE)"}',
    }


@app.post("/api/autopilot/stop")
async def stop_autopilot():
    """Stop the autopilot scheduler."""
    global autopilot_task, autopilot_running

    if not autopilot_running:
        return {'status': 'not_running'}

    if autopilot_task:
        autopilot_task.cancel()
        autopilot_running = False

    return {'status': 'stopped'}


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/config")
async def get_config():
    """Current fund configuration."""
    return {
        'allocation': {
            'etf_pct': config.PORTFOLIO_ALLOCATION['etf'] * 100,
            'stock_pct': config.PORTFOLIO_ALLOCATION['stocks'] * 100,
            'leveraged_pct': config.PORTFOLIO_ALLOCATION['leveraged'] * 100,
        },
        'risk': {
            'kill_switch_dd': config.KILL_SWITCH_DD * 100,
            'kill_switch_daily': config.KILL_SWITCH_DAILY * 100,
            'max_ticker_weight': config.MAX_TICKER_WEIGHT * 100,
            'max_sleeve_weight': config.MAX_SLEEVE_WEIGHT * 100,
            'leveraged_daily_loss': config.LEVERAGED_DAILY_LOSS_LIMIT * 100,
            'leveraged_trailing_stop': config.LEVERAGED_TRAILING_STOP * 100,
        },
        'scheduler': {
            'scan_interval': config.SCAN_INTERVAL_MINUTES,
            'market_open': config.MARKET_OPEN_TRADE_TIME,
            'market_close': config.MARKET_CLOSE_TIME,
        },
        'universe': {
            'etf_tickers': config.ETF_TICKERS,
            'stock_tickers': config.STOCK_TICKERS,
            'leveraged_tickers': config.LEVERAGED_TICKERS,
            'total_tickers': len(config.ETF_TICKERS) + len(config.STOCK_TICKERS) + len(config.LEVERAGED_TICKERS),
        },
        'strategies': config.STRATEGY_ASSIGNMENTS,
        'leveraged': {
            'capital': config.LEVERAGED_CAPITAL,
            'max_per_position': config.LEVERAGED_MAX_PER_POSITION,
            'max_hold_days': config.LEVERAGED_MAX_HOLD_DAYS,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
#  WEBSOCKET — Real-time updates
# ══════════════════════════════════════════════════════════════════════════════
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real-time portfolio updates every 30 seconds."""
    await ws.accept()
    connected_ws.append(ws)
    log.info(f"WebSocket connected ({len(connected_ws)} clients)")

    try:
        while True:
            # Send portfolio snapshot
            acct = client.get_account()
            positions = client.get_positions()

            etf_total = sum(p['market_value'] for t, p in positions.items()
                           if t in config.ETF_TICKERS)
            stock_total = sum(p['market_value'] for t, p in positions.items()
                             if t in config.STOCK_TICKERS)
            lev_total = sum(p['market_value'] for t, p in positions.items()
                           if t in config.LEVERAGED_TICKERS)

            snapshot = {
                'type': 'portfolio_update',
                'portfolio_value': acct['portfolio_value'],
                'daily_pnl': acct['daily_pnl'],
                'daily_pnl_pct': acct['daily_pnl_pct'],
                'cash': acct['cash'],
                'etf_total': etf_total,
                'stock_total': stock_total,
                'lev_total': lev_total,
                'positions_count': len(positions),
                'market_open': client.is_market_open(),
                'autopilot_running': autopilot_running,
                'timestamp': datetime.now().isoformat(),
            }

            await ws.send_json(snapshot)
            await asyncio.sleep(30)

    except WebSocketDisconnect:
        connected_ws.remove(ws)
        log.info(f"WebSocket disconnected ({len(connected_ws)} clients)")


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH + META
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/health")
async def health():
    return {
        'status': 'ok',
        'fund': config.FUND_NAME,
        'market_open': client.is_market_open(),
        'autopilot': autopilot_running,
        'timestamp': datetime.now().isoformat(),
    }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
