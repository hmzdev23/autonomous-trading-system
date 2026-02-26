'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { fetchAPI } from '@/lib/api';

export default function SettingsPage() {
    const [config, setConfig] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchAPI('/api/config')
            .then(setConfig)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="dashboard-layout">
                <Sidebar />
                <main className="main-content">
                    <div className="loading"><div className="spinner" /> Loading configuration...</div>
                </main>
            </div>
        );
    }

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h2>Settings</h2>
                        <div className="subtitle">Fund configuration and risk parameters</div>
                    </div>
                </div>

                <div className="grid-2">
                    {/* Allocation */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Portfolio Allocation</h3>
                        </div>
                        <SettingRow
                            label="ETFs & Index Funds"
                            value={`${config?.allocation?.etf_pct || 70}%`}
                            detail="VOO, QQQ, SCHD, FTXL, XLE, SPEM, EWZ, EWY"
                        />
                        <SettingRow
                            label="Individual Stocks"
                            value={`${config?.allocation?.stock_pct || 20}%`}
                            detail="AAPL, MSFT, NVDA, GOOGL, JPM, GS, BAC, XOM, CVX, AMZN, TSLA, SNDK, AXTI, ASML"
                        />
                        <SettingRow
                            label="Leveraged ETFs"
                            value={`${config?.allocation?.leveraged_pct || 10}%`}
                            detail="TQQQ, SOXL, UPRO, SPXL, TECL"
                        />
                    </div>

                    {/* Risk */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Risk Controls</h3>
                        </div>
                        <SettingRow
                            label="Portfolio Drawdown Kill Switch"
                            value={`${config?.risk?.kill_switch_dd || 15}%`}
                            detail="Halts all trading if portfolio drops by this amount"
                        />
                        <SettingRow
                            label="Daily Loss Kill Switch"
                            value={`${config?.risk?.kill_switch_daily || 3}%`}
                            detail="Halts trading for the day on this daily loss"
                        />
                        <SettingRow
                            label="Max Position Weight"
                            value={`${config?.risk?.max_ticker_weight || 15}%`}
                            detail="Maximum allocation per individual ticker"
                        />
                        <SettingRow
                            label="Leveraged Daily Loss"
                            value={`${config?.risk?.leveraged_daily_loss || 2}%`}
                            detail="Daily loss limit on leveraged ETF bucket"
                        />
                        <SettingRow
                            label="Leveraged Trailing Stop"
                            value={`${config?.risk?.leveraged_trailing_stop || 5}%`}
                            detail="Trailing stop on leveraged positions"
                        />
                    </div>
                </div>

                <div style={{ height: '20px' }} />

                <div className="grid-2">
                    {/* Scheduler */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Scheduler</h3>
                        </div>
                        <SettingRow
                            label="Scan Interval"
                            value={`${config?.scheduler?.scan_interval || 15} min`}
                            detail="How often leveraged ETFs are scanned intraday"
                        />
                        <SettingRow
                            label="Market Open Trade"
                            value={config?.scheduler?.market_open || '09:31'}
                            detail="Time to execute core portfolio trades"
                        />
                        <SettingRow
                            label="Market Close Cleanup"
                            value={config?.scheduler?.market_close || '15:55'}
                            detail="Time to close all leveraged positions"
                        />
                    </div>

                    {/* Leveraged */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Leveraged ETF Config</h3>
                        </div>
                        <SettingRow
                            label="Ring-Fenced Capital"
                            value={`$${(config?.leveraged?.capital || 5000).toLocaleString()}`}
                            detail="Total capital allocated to leveraged sleeve"
                        />
                        <SettingRow
                            label="Max Per Position"
                            value={`$${(config?.leveraged?.max_per_position || 2000).toLocaleString()}`}
                            detail="Maximum capital per leveraged position"
                        />
                        <SettingRow
                            label="Max Hold Days"
                            value={`${config?.leveraged?.max_hold_days || 5} days`}
                            detail="Positions auto-closed after this many days"
                        />
                    </div>
                </div>

                {/* Universe */}
                <div style={{ height: '20px' }} />
                <div className="card">
                    <div className="card-header">
                        <h3>Trading Universe</h3>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            {config?.universe?.total_tickers || 0} tickers
                        </span>
                    </div>

                    <div className="grid-3">
                        <div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                                ETFs ({config?.universe?.etf_tickers?.length || 0})
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {(config?.universe?.etf_tickers || []).map((t: string) => (
                                    <span key={t} className="badge badge-etf">{t}</span>
                                ))}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                                Stocks ({config?.universe?.stock_tickers?.length || 0})
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {(config?.universe?.stock_tickers || []).map((t: string) => (
                                    <span key={t} className="badge badge-stock">{t}</span>
                                ))}
                            </div>
                        </div>
                        <div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase' }}>
                                Leveraged ({config?.universe?.leveraged_tickers?.length || 0})
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                {(config?.universe?.leveraged_tickers || []).map((t: string) => (
                                    <span key={t} className="badge badge-leveraged">{t}</span>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Strategy Assignments */}
                    <div className="section-divider" />
                    <div className="card-header">
                        <h3>Strategy Assignments</h3>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '6px' }}>
                        {config?.strategies && Object.entries(config.strategies as Record<string, string>).map(([ticker, strat]) => (
                            <div key={ticker} style={{
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                padding: '6px 10px', background: 'var(--bg-elevated)',
                                borderRadius: 'var(--radius-sm)', fontSize: '12px',
                            }}>
                                <span style={{ fontWeight: 700, color: 'var(--gold)' }}>{ticker}</span>
                                <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
                                    {strat.replace('_', ' ').slice(0, 12)}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </main>
        </div>
    );
}

function SettingRow({ label, value, detail }: { label: string; value: string; detail: string }) {
    return (
        <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '12px 0', borderBottom: '1px solid var(--border)',
        }}>
            <div>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>{label}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px', maxWidth: '280px' }}>{detail}</div>
            </div>
            <div style={{
                fontWeight: 700, fontSize: '14px', color: 'var(--gold)',
                background: 'var(--gold-dim)', padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
            }}>
                {value}
            </div>
        </div>
    );
}
