'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { fetchAPI } from '@/lib/api';

export default function SignalsPage() {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchAPI('/api/signals')
            .then(setData)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return (
            <div className="dashboard-layout">
                <Sidebar />
                <main className="main-content">
                    <div className="loading"><div className="spinner" /> Generating signals...</div>
                </main>
            </div>
        );
    }

    const signals = data?.signals || {};
    const weights = data?.target_weights || {};

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h2>Live Signals</h2>
                        <div className="subtitle">
                            {data?.active_count || 0} active / {data?.total_count || 0} total ·
                            Invested: {(data?.invested_pct || 0).toFixed(1)}%
                        </div>
                    </div>
                    <button
                        className="btn btn-primary"
                        onClick={() => {
                            setLoading(true);
                            fetchAPI('/api/signals').then(setData).finally(() => setLoading(false));
                        }}
                    >
                        🔄 Regenerate
                    </button>
                </div>

                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: '16px',
                }}>
                    {Object.entries(signals).map(([ticker, detail]: [string, any]) => (
                        <SignalCard
                            key={ticker}
                            ticker={ticker}
                            detail={detail}
                            weight={weights[ticker] || 0}
                        />
                    ))}
                </div>
            </main>
        </div>
    );
}

function SignalCard({ ticker, detail, weight }: {
    ticker: string; detail: any; weight: number;
}) {
    const isLong = detail.signal === 'LONG';

    return (
        <div className="card" style={{
            borderLeft: `3px solid ${isLong ? 'var(--green)' : 'var(--border)'}`,
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                    <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--gold)' }}>{ticker}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                        {detail.strategy?.replace('_', ' ').toUpperCase() || '—'}
                    </span>
                </div>
                <span className={`badge ${isLong ? 'badge-long' : 'badge-flat'}`}>
                    {isLong ? '🟢 LONG' : '⚪ FLAT'}
                </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                <Stat label="Price" value={`$${detail.price?.toFixed(2) || '—'}`} />
                <Stat label="Target Weight" value={`${(weight * 100).toFixed(1)}%`} />
                <Stat label="Activation" value={detail.activation || '—'} />
                <Stat label="Confidence" value={detail.confidence || '—'} />
            </div>
        </div>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <div style={{ color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
            <div style={{ fontWeight: 600, marginTop: '2px' }}>{value}</div>
        </div>
    );
}
