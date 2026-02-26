# Strategy Assignments — PDF Analysis Report

> **Source:** *151 Trading Strategies* — Zura Kakushadze & Juan Andrés Serur (2018)
> **Generated:** 2025-02-24
> **PDF Location:** `StrategiesBook.pdf`

---

## Strategies Extracted from PDF

The following strategies were identified as directly applicable to our equity/ETF universe of 20 tickers. The PDF is a comprehensive encyclopedia of 151 strategies — we selected the **4 most implementable** for our asset classes.

### 1. Two Moving Average Crossover (§3.12)

| Field | Value |
|-------|-------|
| **Type** | Momentum / Trend Following |
| **PDF Section** | 3.12 — Strategy: Two Moving Averages |
| **Entry Rule** | Long when MA(T') > MA(T) (fast crosses above slow = Golden Cross) |
| **Exit Rule** | Flat when MA(T') < MA(T) (fast crosses below slow = Death Cross) |
| **Stop-Loss** | Liquidate if price falls > Δ% below previous day close (PDF Eq. 323, Δ=2%) |
| **Parameters** | T'=50 (fast), T=200 (slow), Δ=8% (widened for daily swing tolerance) |
| **PDF Variants** | SMA or EMA (Eq. 319-320); 3-MA filter variant (§3.13, Eq. 324) |
| **Best For** | Strong-trend, liquid assets with persistent momentum |

**PDF Formula (Eq. 322-323):**
```
Signal = LONG   if MA(T') > MA(T)
Signal = FLAT   if MA(T') < MA(T)
Stop:    Liquidate if P < (1 - Δ) × P_prev
```

### 2. Mean Reversion via Z-Score (§3.9, §3.10, §10.3)

| Field | Value |
|-------|-------|
| **Type** | Mean Reversion / Contrarian |
| **PDF Section** | 3.9 (Mean Reversion), 3.10 (Weighted Regression), 10.3 (Contrarian Trading) |
| **Entry Rule** | Long when z-score < -ENTRY_Z (oversold) |
| **Exit Rule** | Exit when z-score reverts to > -EXIT_Z |
| **Trend Filter** | Only long when price > 200-day SMA (avoid downtrends) |
| **Volume Filter** | Only enter if volume > 20-day average volume |
| **Max Hold** | Force exit after MAX_HOLD_DAYS |
| **Parameters** | Lookback=20, Entry_Z=2.0, Exit_Z=0.5, Max_Hold=15 days |
| **Best For** | Assets with mean-reverting behavior, range-bound trading |

**PDF Foundation (§3.9-3.10):**
```
z_score = (price - rolling_mean(N)) / rolling_std(N)
Demeaned returns: R̃ᵢ = Rᵢ - (1/N)∑Rⱼ  (cluster-neutral, Eq. 310)
Weights: zᵢ = 1/σᵢ²  (inverse variance, Eq. 316)
```

### 3. Sector Momentum Rotation with MA Filter (§4.1.1)

| Field | Value |
|-------|-------|
| **Type** | Momentum / Rotation |
| **PDF Section** | 4.1.1 — Sector Momentum Rotation with MA Filter |
| **Entry Rule** | Rank ETFs by cumulative return over T months; buy top-decile if price > MA(T') |
| **Exit Rule** | Sell when ETF drops out of top decile OR price < MA(T') |
| **Fallback** | If market (VOO) < 200-day MA, move to cash |
| **Parameters** | T=6-12 months momentum lookback, T'=100-200 day MA filter |
| **Best For** | ETFs with sector exposure, rotation-friendly |

**PDF Formula (Eq. 362-363):**
```
R_cum_i = cumulative return of ETF i over T months
Rule = Buy top-decile ETFs if P > MA(T')
        Buy uncorrelated ETF if P ≤ MA(T')
```

### 4. Multi-Asset Trend Following (§4.6)

| Field | Value |
|-------|-------|
| **Type** | Trend Following / Momentum |
| **PDF Section** | 4.6 — Multi-asset trend following |
| **Entry Rule** | Long ETFs with positive R_cum; only if P > MA(T') |
| **Weighting** | w_i = γ × R_cum_i / σ_i (momentum-scaled, vol-adjusted, Eq. 372) |
| **Exit Rule** | Remove when R_cum turns negative or P < MA(T') |
| **Parameters** | T=6 months momentum, T'=200-day MA, w_max=15% |
| **Best For** | Diversified multi-asset ETF portfolios |

**PDF Formula (Eq. 371-373):**
```
w_i = γ₁ × R_cum_i                    (pure momentum weighting)
w_i = γ₂ × R_cum_i / σ_i              (risk-adjusted momentum)
w_i = γ₃ × R_cum_i / σ_i²             (Sharpe-optimized, diagonal cov)
Constraint: Σwᵢ = 1, wᵢ ≤ w_max
```

---

## Strategy-to-Ticker Assignments

### Decision Logic

1. **PDF explicitly recommends** → use that strategy
2. **Strong trend + high liquidity** → SMA Momentum (Two MA Crossover)
3. **Weak trend + mean-reverting** → Mean Reversion (Z-Score)
4. **ETFs with sector exposure** → Sector Momentum Rotation
5. **High volatility** → tighter stops, smaller weights via allocator

### Assignment Table

| Ticker | Name | Sleeve | Assigned Strategy | Rationale |
|--------|------|--------|-------------------|-----------|
| **VOO** | S&P 500 ETF | ETF (Broad) | SMA Momentum | Strong trend, core market, PDF §3.12 ideal for liquid broad indices |
| **QQQ** | Nasdaq 100 ETF | ETF (Broad) | SMA Momentum | Strong trend, growth-heavy, same logic as VOO |
| **FTXL** | Nasdaq Semi ETF | ETF (Sector) | Sector Momentum Rotation | High vol cyclical sector ETF, PDF §4.1.1 designed for sector rotation |
| **SCHD** | Dividend ETF | ETF (Income) | Mean Reversion | Defensive income, weak trend, mean-reverts around yield levels |
| **SPEM** | Emerging Markets ETF | ETF (EM) | Mean Reversion | High vol, weak trend, EM assets tend to mean-revert (PDF §10.3) |
| **ZEB** | BMO Banks ETF | ETF (Sector) | Sector Momentum Rotation | Sector-specific financials ETF, rotation-friendly |
| **XLE** | Energy Sector ETF | ETF (Sector) | Sector Momentum Rotation | Sector ETF, commodity-correlated, rotation strategy fits |
| **AAPL** | Apple | Tech (Megacap) | SMA Momentum | Strong trend, highly liquid megacap, PDF §3.12 two-MA strategy |
| **MSFT** | Microsoft | Tech (Megacap) | SMA Momentum | Same as AAPL — persistent trend, liquid |
| **NVDA** | NVIDIA | Tech (High-Vol) | SMA Momentum | Strong trend despite high vol — wider stop-loss (10%) |
| **GOOGL** | Alphabet | Tech (Megacap) | SMA Momentum | Strong trend, liquid, same as AAPL/MSFT |
| **JPM** | JPMorgan | Financials | Mean Reversion | Medium vol, mean-reverting sector behavior (PDF §3.9-3.10) |
| **GS** | Goldman Sachs | Financials | Mean Reversion | Same as JPM — financials exhibit mean-reversion |
| **BAC** | Bank of America | Financials | Mean Reversion | Same as JPM/GS |
| **XOM** | ExxonMobil | Energy | Mean Reversion | Commodity-correlated, mean reversion around fundamental value |
| **CVX** | Chevron | Energy | Mean Reversion | Same as XOM |
| **AMZN** | Amazon | Consumer | SMA Momentum | Strong trend, growth stock, momentum strategy appropriate |
| **TSLA** | Tesla | Consumer | SMA Momentum | Strong trend, high vol — wider stop-loss (10%), smaller allocation |

### Strategy Summary

| Strategy | Tickers | Count |
|----------|---------|-------|
| SMA Momentum (§3.12) | VOO, QQQ, AAPL, MSFT, NVDA, GOOGL, AMZN, TSLA | 8 |
| Mean Reversion (§3.9) | SCHD, SPEM, JPM, GS, BAC, XOM, CVX | 7 |
| Sector Momentum Rotation (§4.1.1) | FTXL, ZEB, XLE | 3 |

> **Note:** Multi-Asset Trend Following (§4.6) is integrated into the allocation engine rather than assigned to specific tickers. Its inverse-vol weighting formula (Eq. 372) directly informs our `InverseVolAllocator`.

---

## Parameters (PDF-Derived)

### SMA Momentum
```
SMA_FAST       = 50    (T' from PDF §3.12)
SMA_SLOW       = 200   (T from PDF §3.12)
STOP_LOSS      = 0.08  (Δ from PDF Eq. 323, widened from 2% for daily)
STOP_LOSS_HV   = 0.10  (for high-vol tickers: NVDA, TSLA)
```

### Mean Reversion
```
MR_LOOKBACK    = 20    (rolling window for z-score)
MR_ENTRY_Z     = 2.0   (entry threshold, consistent with 2σ Bollinger)
MR_EXIT_Z      = 0.5   (exit when price approaches mean)
MR_MAX_HOLD    = 15    (max holding period in days)
MR_STOP_LOSS   = 0.05  (tighter stop for mean-reversion)
MR_ALLOW_SHORT = False  (long-only for our capital level)
```

### Sector Momentum Rotation
```
SM_LOOKBACK    = 126   (6 months ≈ 126 trading days, PDF T=6-12 months)
SM_MA_FILTER   = 200   (long-term MA filter, PDF T'=100-200 days)
SM_REBALANCE   = 'monthly'  (monthly rotation)
```

---

## Gaps & Fallback Decisions

| Gap | Decision | Fallback |
|-----|----------|----------|
| PDF does not specify exact stop-loss % | Used 8% (standard) for momentum, 5% for mean reversion | Prompt defaults |
| PDF uses daily rebalancing for contrarian (§10.3) | Adapted to daily signals with monthly allocation rebalance | Practical constraint |
| ZEB is Canadian (TSX) | Include in backtests via yfinance (ZEB.TO), exclude from live Alpaca | Documented |
| PDF IBS strategy (§4.4) requires sorting across ETFs | Merged IBS logic into mean-reversion z-score approach | Functional equivalent |

---

## Disclaimer

*Strategy assignments derived from "151 Trading Strategies" by Kakushadze & Serur (2018). Backtest results are hypothetical and do not represent actual trading. Past performance does not guarantee future results. This is not financial advice.*
