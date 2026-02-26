'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { fetchAPI } from '@/lib/api';

export default function PerformancePage() {
    const [portfolio, setPortfolio] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchAPI('/api/portfolio')
            .then(setPortfolio)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="dashboard-layout">
                <Sidebar />
                <main className="main-content">
                    <div className="loading"><div className="spinner" /> Loading performance data...</div>
                </main>
            </div>
        );
    }

    const positions = [
        ...(portfolio?.positions?.etf || []),
        ...(portfolio?.positions?.stocks || []),
        ...(portfolio?.positions?.leveraged || []),
    ];

    const totalPnL = positions.reduce((sum: number, p: any) => sum + (p.pnl || 0), 0);
    const winners = positions.filter((p: any) => p.pnl > 0);
    const losers = positions.filter((p: any) => p.pnl < 0);
    const bestPerf = [...positions].sort((a: any, b: any) => b.pnl_pct - a.pnl_pct).slice(0, 5);
    const worstPerf = [...positions].sort((a: any, b: any) => a.pnl_pct - b.pnl_pct).slice(0, 5);

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h2>Performance</h2>
                        <div className="subtitle">Portfolio performance and risk analytics</div>
                    </div>
                </div>

                {/* Summary Metrics */}
                <div className="metrics-grid">
                    <div className={`metric-card ${totalPnL >= 0 ? 'green' : 'red'}`}>
                        <div className="metric-label">Total P&amp;L</div>
                        <div className="metric-value sm">
                            {totalPnL >= 0 ? '+' : ''}${totalPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </div>
                    </div>
                    <div className="metric-card green">
                        <div className="metric-label">Winners</div>
                        <div className="metric-value sm">{winners.length}</div>
                        <div className="metric-change positive">
                            +${winners.reduce((s: number, p: any) => s + p.pnl, 0).toFixed(2)}
                        </div>
                    </div>
                    <div className="metric-card red">
                        <div className="metric-label">Losers</div>
                        <div className="metric-value sm">{losers.length}</div>
                        <div className="metric-change negative">
                            ${losers.reduce((s: number, p: any) => s + p.pnl, 0).toFixed(2)}
                        </div>
                    </div>
                    <div className="metric-card blue">
                        <div className="metric-label">Win Rate</div>
                        <div className="metric-value sm">
                            {positions.length > 0 ? ((winners.length / positions.length) * 100).toFixed(0) : 0}%
                        </div>
                    </div>
                </div>

                {/* Best / Worst Performers */}
                <div className="grid-2" style={{ marginBottom: '24px' }}>
                    <div className="card">
                        <div className="card-header">
                            <h3>🏆 Top Performers</h3>
                        </div>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th style={{ textAlign: 'right' }}>P&amp;L</th>
                                    <th style={{ textAlign: 'right' }}>Return</th>
                                </tr>
                            </thead>
                            <tbody>
                                {bestPerf.map((p: any) => (
                                    <tr key={p.ticker}>
                                        <td className="ticker">{p.ticker}</td>
                                        <td style={{ textAlign: 'right' }} className="positive">
                                            +${p.pnl.toFixed(2)}
                                        </td>
                                        <td style={{ textAlign: 'right' }} className="positive">
                                            ▲ {p.pnl_pct.toFixed(2)}%
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <h3>📉 Worst Performers</h3>
                        </div>
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Ticker</th>
                                    <th style={{ textAlign: 'right' }}>P&amp;L</th>
                                    <th style={{ textAlign: 'right' }}>Return</th>
                                </tr>
                            </thead>
                            <tbody>
                                {worstPerf.map((p: any) => (
                                    <tr key={p.ticker}>
                                        <td className="ticker">{p.ticker}</td>
                                        <td style={{ textAlign: 'right' }} className="negative">
                                            ${p.pnl.toFixed(2)}
                                        </td>
                                        <td style={{ textAlign: 'right' }} className="negative">
                                            ▼ {Math.abs(p.pnl_pct).toFixed(2)}%
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Category Performance */}
                <div className="card">
                    <div className="card-header">
                        <h3>Performance by Sleeve</h3>
                    </div>
                    <div className="grid-3" style={{ marginTop: '8px' }}>
                        {(['etf', 'stocks', 'leveraged'] as const).map((cat) => {
                            const catPositions = portfolio?.positions?.[cat] || [];
                            const catPnL = catPositions.reduce((s: number, p: any) => s + (p.pnl || 0), 0);
                            const catValue = catPositions.reduce((s: number, p: any) => s + (p.market_value || 0), 0);
                            const catPnLPct = catValue > 0 ? (catPnL / (catValue - catPnL)) * 100 : 0;

                            return (
                                <div key={cat} style={{
                                    background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)',
                                    padding: '16px', border: '1px solid var(--border)',
                                }}>
                                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '8px' }}>
                                        {cat === 'etf' ? '🏛 ETFs' : cat === 'stocks' ? '📊 Stocks' : '⚡ Leveraged'}
                                    </div>
                                    <div style={{ fontSize: '20px', fontWeight: 700, color: catPnL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                        {catPnL >= 0 ? '+' : ''}${catPnL.toFixed(2)}
                                    </div>
                                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                                        {catPnLPct >= 0 ? '▲' : '▼'} {Math.abs(catPnLPct).toFixed(2)}% · {catPositions.length} positions
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </main>
        </div>
    );
}
