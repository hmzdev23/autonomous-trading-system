'use client';

import { useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { fetchAPI } from '@/lib/api';

export default function TradesPage() {
    const [ticker, setTicker] = useState('');
    const [side, setSide] = useState<'buy' | 'sell'>('buy');
    const [amount, setAmount] = useState('');
    const [dryRun, setDryRun] = useState(true);
    const [result, setResult] = useState<any>(null);
    const [rebalResult, setRebalResult] = useState<any>(null);
    const [executing, setExecuting] = useState(false);

    const executeTrade = async () => {
        if (!ticker || !amount) return;
        setExecuting(true);
        try {
            const res = await fetchAPI('/api/trades/execute', {
                method: 'POST',
                body: JSON.stringify({
                    ticker: ticker.toUpperCase(),
                    side,
                    amount: parseFloat(amount),
                    dry_run: dryRun,
                }),
            });
            setResult(res);
        } catch (err: any) {
            setResult({ error: err.message });
        } finally {
            setExecuting(false);
        }
    };

    const triggerRebalance = async () => {
        setExecuting(true);
        try {
            const res = await fetchAPI(`/api/trades/rebalance?dry_run=${dryRun}`, {
                method: 'POST',
            });
            setRebalResult(res);
        } catch (err: any) {
            setRebalResult({ error: err.message });
        } finally {
            setExecuting(false);
        }
    };

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h2>Trade Center</h2>
                        <div className="subtitle">Execute trades and trigger rebalances</div>
                    </div>
                </div>

                <div className="grid-2">
                    {/* Manual Trade Form */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Execute Trade</h3>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', cursor: 'pointer' }}>
                                <input
                                    type="checkbox"
                                    checked={dryRun}
                                    onChange={(e) => setDryRun(e.target.checked)}
                                    style={{ accentColor: 'var(--gold)' }}
                                />
                                <span style={{ color: dryRun ? 'var(--amber)' : 'var(--green)' }}>
                                    {dryRun ? '🔒 Dry Run' : '🔓 LIVE'}
                                </span>
                            </label>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            <input
                                placeholder="Ticker (e.g. AAPL)"
                                value={ticker}
                                onChange={(e) => setTicker(e.target.value)}
                                style={{
                                    background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                                    borderRadius: 'var(--radius-sm)', padding: '10px 14px',
                                    color: 'var(--text-primary)', fontSize: '14px', fontWeight: 600,
                                    outline: 'none', textTransform: 'uppercase',
                                }}
                            />

                            <div style={{ display: 'flex', gap: '8px' }}>
                                <button
                                    className={`btn ${side === 'buy' ? 'btn-success' : 'btn-outline'}`}
                                    onClick={() => setSide('buy')}
                                    style={{ flex: 1 }}
                                >
                                    BUY
                                </button>
                                <button
                                    className={`btn ${side === 'sell' ? 'btn-danger' : 'btn-outline'}`}
                                    onClick={() => setSide('sell')}
                                    style={{ flex: 1 }}
                                >
                                    SELL
                                </button>
                            </div>

                            <input
                                placeholder="Amount ($)"
                                type="number"
                                value={amount}
                                onChange={(e) => setAmount(e.target.value)}
                                style={{
                                    background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                                    borderRadius: 'var(--radius-sm)', padding: '10px 14px',
                                    color: 'var(--text-primary)', fontSize: '14px', outline: 'none',
                                }}
                            />

                            <button
                                className="btn btn-primary"
                                onClick={executeTrade}
                                disabled={executing || !ticker || !amount}
                                style={{ width: '100%', justifyContent: 'center', padding: '12px', fontSize: '14px' }}
                            >
                                {executing ? '⏳ Executing...' : `${side.toUpperCase()} ${ticker.toUpperCase() || 'TICKER'}`}
                            </button>
                        </div>

                        {result && (
                            <div style={{
                                marginTop: '16px', padding: '12px',
                                background: result.error ? 'var(--red-dim)' : 'var(--green-dim)',
                                borderRadius: 'var(--radius-sm)', fontSize: '12px',
                            }}>
                                <pre style={{ whiteSpace: 'pre-wrap', color: result.error ? 'var(--red)' : 'var(--green)' }}>
                                    {JSON.stringify(result, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>

                    {/* Rebalance */}
                    <div className="card">
                        <div className="card-header">
                            <h3>Portfolio Rebalance</h3>
                        </div>
                        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.6 }}>
                            Run the full signal engine and rebalance the portfolio based on current strategy signals.
                            This will generate buy/sell orders to align positions with target weights.
                        </p>

                        <button
                            className="btn btn-primary"
                            onClick={triggerRebalance}
                            disabled={executing}
                            style={{ width: '100%', justifyContent: 'center', padding: '12px', fontSize: '14px', marginBottom: '12px' }}
                        >
                            {executing ? '⏳ Running...' : `🔄 ${dryRun ? 'DRY RUN' : 'LIVE'} Rebalance`}
                        </button>

                        {rebalResult && (
                            <div style={{
                                padding: '12px',
                                background: 'var(--bg-elevated)',
                                borderRadius: 'var(--radius-sm)', fontSize: '12px',
                                maxHeight: '300px', overflow: 'auto',
                            }}>
                                <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)' }}>
                                    {JSON.stringify(rebalResult, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
}
