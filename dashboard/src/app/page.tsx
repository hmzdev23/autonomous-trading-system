'use client';

import { useEffect, useState, useCallback } from 'react';
import Sidebar from '@/components/Sidebar';
import EquityChart from '@/components/EquityChart';
import { fetchAPI, connectWebSocket } from '@/lib/api';

export default function DashboardPage() {
    const [portfolio, setPortfolio] = useState<any>(null);
    const [wsData, setWsData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    const loadPortfolio = useCallback(async () => {
        try {
            const data = await fetchAPI('/api/portfolio');
            setPortfolio(data);
        } catch (err) {
            console.error('Failed to load portfolio:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadPortfolio();
        const iv = setInterval(loadPortfolio, 60000);
        const ws = connectWebSocket((data) => setWsData(data));
        return () => { clearInterval(iv); ws?.close(); };
    }, [loadPortfolio]);

    if (loading) {
        return (
            <div className="dashboard-layout">
                <Sidebar />
                <main className="main-content">
                    <div className="loading"><div className="spinner" /> Loading portfolio...</div>
                </main>
            </div>
        );
    }

    const acct = wsData || portfolio?.account || {};
    const alloc = portfolio?.allocation || {};
    const positions = portfolio?.positions || {};

    const pnlPositive = (acct.daily_pnl || 0) >= 0;

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                {/* Page Header */}
                <div className="page-header">
                    <div>
                        <h2>Portfolio Overview</h2>
                        <div className="subtitle">
                            {portfolio?.total_positions || 0} positions · Last updated {new Date().toLocaleTimeString()}
                        </div>
                    </div>
                    <button className="btn btn-outline" onClick={loadPortfolio}>
                        ↻ Refresh
                    </button>
                </div>

                {/* Hero Metrics */}
                <div className="metrics-grid">
                    <div className="metric-card">
                        <div className="metric-label">Portfolio Value</div>
                        <div className="metric-value">
                            ${(acct.portfolio_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    </div>

                    <div className={`metric-card ${pnlPositive ? 'green' : 'red'}`}>
                        <div className="metric-label">Today&apos;s P&amp;L</div>
                        <div className="metric-value sm">
                            {pnlPositive ? '+' : ''}${(acct.daily_pnl || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                        <div className={`metric-change ${pnlPositive ? 'positive' : 'negative'}`}>
                            {pnlPositive ? '▲' : '▼'} {Math.abs(acct.daily_pnl_pct || 0).toFixed(2)}%
                        </div>
                    </div>

                    <div className="metric-card blue">
                        <div className="metric-label">Cash Available</div>
                        <div className="metric-value sm">
                            ${(acct.cash || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    </div>

                    <div className="metric-card teal">
                        <div className="metric-label">Market Status</div>
                        <div className="metric-value sm" style={{ fontSize: '18px' }}>
                            {acct.market_open ? '🟢 Open' : '🔴 Closed'}
                        </div>
                    </div>
                </div>

                {/* Equity Curve Chart */}
                <div style={{ marginBottom: '24px' }}>
                    <EquityChart />
                </div>

                {/* Allocation Breakdown */}
                <div className="grid-2" style={{ marginBottom: '24px' }}>
                    <div className="card">
                        <div className="card-header">
                            <h3>Allocation vs. Target</h3>
                        </div>
                        <AllocBar
                            label="ETFs & Index Funds"
                            actual={alloc.etf?.pct || 0}
                            target={70}
                            value={alloc.etf?.value || 0}
                            color="var(--blue)"
                        />
                        <AllocBar
                            label="Individual Stocks"
                            actual={alloc.stocks?.pct || 0}
                            target={20}
                            value={alloc.stocks?.value || 0}
                            color="var(--gold)"
                        />
                        <AllocBar
                            label="Leveraged ETFs"
                            actual={alloc.leveraged?.pct || 0}
                            target={10}
                            value={alloc.leveraged?.value || 0}
                            color="var(--purple)"
                        />
                        <AllocBar
                            label="Cash Reserve"
                            actual={alloc.cash?.pct || 0}
                            target={0}
                            value={alloc.cash?.value || 0}
                            color="var(--text-muted)"
                        />
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <h3>Sleeve Breakdown</h3>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <SleeveCard
                                label="ETFs"
                                count={alloc.etf?.count || 0}
                                value={alloc.etf?.value || 0}
                                pct={alloc.etf?.pct || 0}
                                badge="badge-etf"
                            />
                            <SleeveCard
                                label="Stocks"
                                count={alloc.stocks?.count || 0}
                                value={alloc.stocks?.value || 0}
                                pct={alloc.stocks?.pct || 0}
                                badge="badge-stock"
                            />
                            <SleeveCard
                                label="Leveraged"
                                count={alloc.leveraged?.count || 0}
                                value={alloc.leveraged?.value || 0}
                                pct={alloc.leveraged?.pct || 0}
                                badge="badge-leveraged"
                            />
                            <SleeveCard
                                label="Cash"
                                count={0}
                                value={alloc.cash?.value || 0}
                                pct={alloc.cash?.pct || 0}
                                badge="badge-flat"
                            />
                        </div>
                    </div>
                </div>

                {/* Positions Table */}
                <div className="card">
                    <div className="card-header">
                        <h3>All Positions</h3>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            {portfolio?.total_positions || 0} holdings
                        </span>
                    </div>
                    <PositionTable
                        positions={[
                            ...(positions.etf || []),
                            ...(positions.stocks || []),
                            ...(positions.leveraged || []),
                            ...(positions.other || []),
                        ]}
                    />
                </div>
            </main>
        </div>
    );
}


/* ── Sub-components ────────────────────────────────── */

function AllocBar({ label, actual, target, value, color }: {
    label: string; actual: number; target: number; value: number; color: string;
}) {
    return (
        <div className="alloc-bar-container">
            <div className="alloc-bar-label">
                <span>{label}</span>
                <span>{actual.toFixed(1)}% / {target}% · ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
            </div>
            <div className="alloc-bar">
                <div
                    className="alloc-bar-fill"
                    style={{ width: `${Math.min(actual, 100)}%`, background: color }}
                />
                {target > 0 && (
                    <div className="alloc-bar-target" style={{ left: `${target}%` }} />
                )}
            </div>
        </div>
    );
}

function SleeveCard({ label, count, value, pct, badge }: {
    label: string; count: number; value: number; pct: number; badge: string;
}) {
    return (
        <div style={{
            background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)',
            padding: '14px', border: '1px solid var(--border)'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span className={`badge ${badge}`}>{label}</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{count} pos.</span>
            </div>
            <div style={{ fontSize: '18px', fontWeight: 700 }}>
                ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {pct.toFixed(1)}% of portfolio
            </div>
        </div>
    );
}

function PositionTable({ positions }: { positions: any[] }) {
    if (!positions.length) return <div className="loading">No positions</div>;

    const sorted = [...positions].sort((a, b) => b.market_value - a.market_value);

    return (
        <div style={{ overflowX: 'auto' }}>
            <table className="data-table">
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th>Category</th>
                        <th style={{ textAlign: 'right' }}>Value</th>
                        <th style={{ textAlign: 'right' }}>P&amp;L</th>
                        <th style={{ textAlign: 'right' }}>P&amp;L %</th>
                        <th style={{ textAlign: 'right' }}>Shares</th>
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((p) => {
                        const positive = p.pnl >= 0;
                        return (
                            <tr key={p.ticker}>
                                <td className="ticker">{p.ticker}</td>
                                <td>
                                    <span className={`badge badge-${p.category}`}>
                                        {p.category?.toUpperCase()}
                                    </span>
                                </td>
                                <td style={{ textAlign: 'right' }}>
                                    ${p.market_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                                <td style={{ textAlign: 'right' }} className={positive ? 'positive' : 'negative'}>
                                    {positive ? '+' : ''}${p.pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </td>
                                <td style={{ textAlign: 'right' }} className={positive ? 'positive' : 'negative'}>
                                    {positive ? '▲' : '▼'} {Math.abs(p.pnl_pct).toFixed(2)}%
                                </td>
                                <td style={{ textAlign: 'right', color: 'var(--text-secondary)' }}>
                                    {p.qty.toFixed(2)}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
