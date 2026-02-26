<div align="center">

# HR Capital

**Autonomous Multi-Strategy Algorithmic Trading System**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-111111?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-111111?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-111111?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![Alpaca](https://img.shields.io/badge/Alpaca-Markets-111111?style=flat-square)](https://alpaca.markets)
[![License: MIT](https://img.shields.io/badge/License-MIT-111111?style=flat-square)](LICENSE)

A fully autonomous hedge fund system that runs 6 quantitative strategies across 22+ tickers with live execution via Alpaca Markets, real-time monitoring through a custom dashboard, and institutional-grade backtesting with walk-forward validation.

[Getting Started](#getting-started) · [Architecture](#architecture) · [Strategies](#strategies) · [Backtesting](#backtesting) · [Dashboard](#dashboard) · [Configuration](#configuration)

</div>

---

## Overview

HR Capital is a production-grade algorithmic trading platform built from scratch in Python. It autonomously manages a diversified portfolio across ETFs, equities, and leveraged instruments using a multi-strategy framework with per-ticker strategy assignment, inverse-volatility and momentum-weighted allocation, and automated risk management.

The system operates on a daily schedule — generating signals, executing trades, rebalancing positions, and monitoring risk — all without manual intervention.

### Key Capabilities

- **6 quantitative strategies** with per-ticker assignment and configurable parameters
- **Vectorised backtesting engine** with slippage modeling, commission tracking, and benchmark comparison
- **Walk-forward validation** to detect overfitting across rolling train/test windows
- **Live execution** via Alpaca Markets API with paper/live trading support
- **Autonomous scheduler** with pre-market data refresh, market-open execution, intraday scanning, and EOD closeout
- **Real-time dashboard** (Next.js + FastAPI) with TradingView-style equity charts, position monitoring, and trade execution
- **Risk management** including kill switches, trailing stops, max drawdown limits, and position sizing constraints
- **macOS LaunchAgent** for fully unattended operation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        HR Capital System                        │
├────────────────┬──────────────────┬─────────────────────────────┤
│   Trading Core │   API Layer      │   Dashboard                 │
│                │                  │                             │
│  strategies/   │  api/main.py     │  dashboard/                 │
│  ├─ aggressive │  FastAPI server  │  Next.js 14 app             │
│  ├─ dual_mom   │  REST + WS       │  ├─ Portfolio view          │
│  ├─ sector_mom │  CORS enabled    │  ├─ Equity chart            │
│  ├─ sma_mom    │                  │  ├─ Signal monitor          │
│  ├─ mean_rev   │  Endpoints:      │  ├─ Trade center            │
│  └─ leveraged  │  /portfolio      │  ├─ Scanner                 │
│                │  /signals        │  ├─ Autopilot controls      │
│  backtester/   │  /trades         │  ├─ Performance             │
│  ├─ engine.py  │  /scanner        │  └─ Settings                │
│  ├─ metrics.py │  /autopilot      │                             │
│  └─ walk_fwd   │  /settings       │                             │
│                │  /health         │                             │
│  portfolio/    │                  │                             │
│  ├─ allocator  ├──────────────────┤                             │
│  ├─ rebalancer │  Broker Layer    │                             │
│  └─ momentum   │  Alpaca Markets  │                             │
│                │  Paper / Live    │                             │
│  scheduler.py  │                  │                             │
│  (Autopilot)   │                  │                             │
└────────────────┴──────────────────┴─────────────────────────────┘
```

### Directory Structure

```
hedge_fund/
├── backtester/
│   ├── engine.py              # Vectorised multi-asset backtesting engine
│   ├── metrics.py             # Sharpe, Sortino, Calmar, VaR, CVaR, drawdown analysis
│   └── walk_forward.py        # Rolling window train/test validation
├── brokers/
│   ├── alpaca_client.py       # Alpaca Markets API wrapper
│   ├── executor.py            # Order execution with retry logic
│   ├── scanner.py             # Intraday leveraged ETF scanner
│   └── signal_engine.py       # Multi-ticker signal generation pipeline
├── data/
│   ├── fetcher.py             # Historical data retrieval (yfinance)
│   └── processor.py           # Technical indicator computation
├── portfolio/
│   ├── allocator.py           # Inverse-volatility allocation
│   ├── momentum_allocator.py  # Momentum-weighted allocation
│   ├── portfolio.py           # Portfolio state management
│   └── rebalancer.py          # Position rebalancing with drift detection
├── strategies/
│   ├── base.py                # Abstract strategy interface
│   ├── aggressive_momentum.py # EMA crossover + MACD + trailing stop
│   ├── dual_momentum.py       # Absolute + relative momentum
│   ├── sector_momentum.py     # Sector rotation with MA filter
│   ├── sma_momentum.py        # SMA 50/200 golden cross
│   ├── mean_reversion.py      # Bollinger Band mean reversion
│   ├── leveraged_momentum.py  # Short-term momentum for 3x ETFs
│   └── registry.py            # Strategy → ticker assignment map
├── config.py                  # All parameters, universe, constraints
├── main.py                    # CLI entry point
└── scheduler.py               # Autonomous trading daemon

api/
└── main.py                    # FastAPI backend (20+ REST endpoints)

dashboard/
└── src/
    ├── app/                   # Next.js 14 pages
    └── components/
        ├── Sidebar.tsx        # Navigation
        └── EquityChart.tsx    # Canvas-rendered TradingView-style chart
```

---

## Strategies

The system implements 6 distinct quantitative strategies, each assigned to specific tickers based on their market characteristics:

| Strategy | Tickers | Logic |
|----------|---------|-------|
| **Aggressive Momentum** | VOO, QQQ, AAPL, MSFT, NVDA, GOOGL, AMZN, TSLA, ASML, SNDK, AXTI | EMA 12/26 crossover + MACD confirmation + 12% trailing stop + RSI exit floor |
| **Dual Momentum** | SCHD, SPEM, EWZ, EWY, JPM, GS, BAC, XOM, CVX | Absolute momentum (vs. risk-free) + relative momentum (vs. benchmark), 63-day lookback |
| **Sector Momentum** | FTXL, ZEB, XLE | Top-fraction sector rotation with 100-day MA trend filter |
| **SMA Momentum** | *(available)* | Golden cross (SMA 50/200) with 8-10% stop loss |
| **Mean Reversion** | *(available)* | Bollinger Band z-score entry/exit with max holding period |
| **Leveraged Momentum** | TQQQ, SOXL, UPRO, SPXL, TECL | Ultra-short EMA 5/13 for 3x ETFs, 5% trailing stop, max 5 day hold |

### Portfolio Allocation

The portfolio is structured in three sleeves with risk-appropriate allocation:

| Sleeve | Target Weight | Tickers | Rebalance |
|--------|--------------|---------|-----------|
| Core ETFs & Index | 70% | VOO, QQQ, SCHD, FTXL, XLE, SPEM, EWZ, EWY | Monthly |
| Individual Stocks | 20% | AAPL, MSFT, NVDA, GOOGL, JPM, GS, BAC, XOM, CVX, AMZN, TSLA, SNDK, AXTI, ASML | Monthly |
| Leveraged ETFs | 10% | TQQQ, SOXL, UPRO, SPXL, TECL | Intraday / 5-day max |

**Allocation methods:**
- **Momentum-weighted** (default): Allocates more capital to higher-momentum tickers
- **Inverse-volatility**: Allocates inversely proportional to recent realized volatility

**Constraints:**
- Max 15% per single ticker
- Max 35% per sleeve
- Min 1% position threshold (below = dropped to cash)

---

## Backtesting

The backtesting engine simulates the full portfolio with realistic execution modeling:

```python
from backtester.engine import BacktestEngine

engine = BacktestEngine(
    start='2021-01-01',
    end='2026-01-01',
    capital=10_000,
    slippage=0.001,    # 10 bps
    commission=1.00,    # $1/trade
)
results = engine.run()
```

### Features

- **Vectorised execution** — processes all tickers simultaneously via NumPy/Pandas
- **No lookahead bias** — signals on day N execute at day N+1 open prices
- **Slippage modeling** — configurable basis point cost on signal changes
- **VOO benchmark** — automatic buy-and-hold comparison
- **Per-ticker decomposition** — individual strategy performance attribution

### Metrics Computed

| Category | Metrics |
|----------|---------|
| **Returns** | Total return, CAGR, best/worst month, annual breakdown |
| **Risk** | Annualised volatility, max drawdown (depth + duration), VaR/CVaR 95% |
| **Risk-Adjusted** | Sharpe ratio, Sortino ratio, Calmar ratio, Information ratio |
| **Benchmark** | Alpha (Jensen's), Beta, correlation to VOO |

### Walk-Forward Validation

Detects overfitting by comparing in-sample vs. out-of-sample Sharpe ratios across rolling windows:

```python
from backtester.walk_forward import walk_forward_validate

wf = walk_forward_validate(results['equity_curve'], train_months=6, test_months=6)
# Returns: avg_train_sharpe, avg_test_sharpe, degradation %, overfitting flag
```

---

## Risk Management

The system enforces multiple layers of risk controls:

| Control | Threshold | Scope |
|---------|-----------|-------|
| **Portfolio Kill Switch** | -15% drawdown | Halts all trading |
| **Daily Loss Limit** | -3% daily P&L | Halts trading for the day |
| **Trailing Stop (Core)** | -12% from peak | Per-position, aggressive momentum |
| **Trailing Stop (Leveraged)** | -5% from peak | Per-position, leveraged ETFs |
| **Max Hold (Leveraged)** | 5 trading days | Decay protection for 3x ETFs |
| **Daily Loss (Leveraged)** | -2% of leveraged capital | Ring-fenced allocation |
| **Position Sizing** | Max 15% per ticker | Concentration limit |

---

## Dashboard

The monitoring dashboard is a Next.js 14 application with a clean, minimal design:

- **Portfolio Overview** — real-time equity, P&L, allocation vs. target bars
- **Equity Chart** — canvas-rendered TradingView-style chart with gradient fill, period selector (1D/1W/1M/3M/1Y/ALL), crosshair hover, OHLC stats, auto-refresh
- **Signals** — live strategy signals across all tickers with confidence indicators
- **Trade Center** — execute manual trades, trigger rebalances, view trade history
- **Scanner** — leveraged ETF intraday scanner with momentum scores
- **Autopilot** — start/stop the autonomous scheduler, view run logs
- **Performance** — historical metrics and attribution analysis
- **Settings** — live configuration tuning (allocation %, kill switch thresholds)

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **Alpaca Markets account** — [Sign up here](https://app.alpaca.markets/signup) (free paper trading account)

### 1. Clone the repository

```bash
git clone https://github.com/hmzdev23/autonomous-trading-system.git
cd autonomous-trading-system
```

### 2. Set up Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API keys

Create a `.env` file in the `hedge_fund/` directory:

```env
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
```

You can get your keys from the [Alpaca Dashboard](https://app.alpaca.markets/paper/dashboard/overview):
1. Sign up for a free account
2. Navigate to **Paper Trading** → **API Keys**
3. Click **Generate New Key**
4. Copy both the API Key and Secret Key into your `.env` file

> **Note:** The system defaults to **paper trading** mode. To switch to live trading, set `ALPACA_PAPER = False` in `config.py`. Only do this if you understand the risks.

### 4. Install dashboard dependencies

```bash
cd dashboard
npm install
cd ..
```

### 5. Start everything

```bash
./start.sh
```

This launches the API server on `http://localhost:8000` and the dashboard on `http://localhost:3000`.

### 6. Run a backtest

```bash
cd hedge_fund
python -c "from backtester.engine import run_backtest; run_backtest()"
```

### 7. Enable autopilot (optional)

To run the trading daemon autonomously:

```bash
cd hedge_fund
python scheduler.py
```

Or install the macOS LaunchAgent for fully unattended operation:

```bash
cp com.hedgefund.autopilot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hedgefund.autopilot.plist
```

---

## Configuration

All system parameters are centralized in `hedge_fund/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `STARTING_CAPITAL` | `10,000` | Initial portfolio value |
| `ALLOCATION_MODE` | `momentum` | `momentum` or `inverse_vol` |
| `REBALANCE_FREQ` | `monthly` | Portfolio rebalance schedule |
| `KILL_SWITCH_DD` | `15%` | Max drawdown before halt |
| `KILL_SWITCH_DAILY` | `3%` | Max daily loss before halt |
| `SLIPPAGE` | `10 bps` | Simulated execution slippage |
| `SCAN_INTERVAL_MINUTES` | `15` | Intraday scanner frequency |
| `LEVERAGED_MAX_HOLD_DAYS` | `5` | Decay protection for 3x ETFs |

Strategy-specific parameters (EMA periods, stop losses, lookback windows) are also configurable in `config.py` and documented inline.

---

## API Reference

The FastAPI backend exposes the following endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/portfolio` | Live portfolio snapshot (positions, allocation, P&L) |
| `GET` | `/api/portfolio/history?period=1D` | Equity curve data for charting |
| `GET` | `/api/signals` | Current strategy signals for all tickers |
| `GET` | `/api/signals/leveraged` | Leveraged ETF scanner signals |
| `GET` | `/api/trades` | Recent trade history |
| `POST` | `/api/trades/execute` | Execute a manual trade |
| `POST` | `/api/trades/rebalance` | Trigger portfolio rebalance |
| `GET` | `/api/scanner` | Scanner status and results |
| `POST` | `/api/scanner/run` | Force an intraday scan |
| `POST` | `/api/autopilot/start` | Start autonomous scheduler |
| `POST` | `/api/autopilot/stop` | Stop autonomous scheduler |
| `GET` | `/api/settings` | Current configuration |
| `POST` | `/api/settings` | Update configuration |
| `GET` | `/api/health` | System health check |

Interactive docs available at `http://localhost:8000/docs` (Swagger UI).

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Trading Engine** | Python 3.10, NumPy, Pandas, yfinance |
| **Broker Integration** | Alpaca Markets REST API (alpaca-trade-api) |
| **API Server** | FastAPI, Uvicorn, Pydantic |
| **Dashboard** | Next.js 14, React, TypeScript, Canvas API |
| **Backtesting** | Custom vectorised engine, Matplotlib |
| **Scheduling** | APScheduler, macOS LaunchAgent (launchd) |
| **Data** | yfinance (historical), Alpaca (live quotes) |

---

## Disclaimer

This project is for **educational and research purposes only**. Algorithmic trading involves substantial risk of loss. Past backtested performance does not guarantee future results. Always use paper trading to test strategies before risking real capital. The author assumes no responsibility for financial losses incurred from using this software.

---

<div align="center">

**Built by [Hamza Rehman](https://github.com/hmzdev23)**

</div>
