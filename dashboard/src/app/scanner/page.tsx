'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { fetchAPI } from '@/lib/api';

export default function ScannerPage() {
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [scanning, setScanning] = useState(false);

    useEffect(() => {
        fetchAPI('/api/scanner')
            .then(setData)
            .catch(console.error)
            .finally(() => setLoading(false));
    }, []);

    const runScan = async (dryRun: boolean) => {
        setScanning(true);
        try {
            const res = await fetchAPI(`/api/scanner/run?dry_run=${dryRun}`, { method: 'POST' });
            setData(res);
        } catch (e) {
            console.error(e);
        } finally {
            setScanning(false);
        }
    };

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h2>Leveraged ETF Scanner</h2>
                        <div className="subtitle">$5K ring-fenced allocation · 3x ETFs · 15-min scan cycle</div>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <button className="btn btn-outline" onClick={() => runScan(true)} disabled={scanning}>
                            {scanning ? '⏳' : '🔍'} Dry Run Scan
                        </button>
                        <button className="btn btn-primary" onClick={() => runScan(false)} disabled={scanning}>
                            {scanning ? '⏳' : '⚡'} Live Scan
                        </button>
                    </div>
                </div>

                {loading ? (
                    <div className="loading"><div className="spinner" /> Scanning leveraged ETFs...</div>
                ) : (
                    <>
                        <div className="metrics-grid">
                            <div className="metric-card">
                                <div className="metric-label">Leveraged Capital</div>
                                <div className="metric-value sm">$5,000</div>
                            </div>
                            <div className="metric-card teal">
                                <div className="metric-label">Active Signals</div>
                                <div className="metric-value sm">
                                    {data?.signals ? Object.values(data.signals as Record<string, string>).filter((s) => s === 'LONG').length : 0} / 5
                                </div>
                            </div>
                            <div className="metric-card blue">
                                <div className="metric-label">Scan Interval</div>
                                <div className="metric-value sm">15 min</div>
                            </div>
                        </div>

                        {data?.signals && (
                            <div className="card">
                                <div className="card-header">
                                    <h3>Leveraged ETF Signals</h3>
                                </div>
                                <table className="data-table">
                                    <thead>
                                        <tr>
                                            <th>Ticker</th>
                                            <th>Name</th>
                                            <th>Signal</th>
                                            <th>Leverage</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {Object.entries(data.signals as Record<string, string>).map(([ticker, signal]) => (
                                            <tr key={ticker}>
                                                <td className="ticker">{ticker}</td>
                                                <td style={{ color: 'var(--text-secondary)' }}>
                                                    {{
                                                        'TQQQ': '3x NASDAQ-100', 'SOXL': '3x Semiconductors',
                                                        'UPRO': '3x S&P 500', 'SPXL': '3x S&P 500',
                                                        'TECL': '3x Technology'
                                                    }[ticker] || ticker}
                                                </td>
                                                <td>
                                                    <span className={`badge ${signal === 'LONG' ? 'badge-long' : 'badge-flat'}`}>
                                                        {signal === 'LONG' ? '🟢 LONG' : '⚪ FLAT'}
                                                    </span>
                                                </td>
                                                <td style={{ color: 'var(--purple)' }}>3x</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </>
                )}
            </main>
        </div>
    );
}
