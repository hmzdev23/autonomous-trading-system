'use client';

import { useEffect, useState } from 'react';
import Sidebar from '@/components/Sidebar';
import { fetchAPI } from '@/lib/api';

export default function AutopilotPage() {
    const [status, setStatus] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [acting, setActing] = useState(false);

    const load = () => {
        fetchAPI('/api/autopilot/status')
            .then(setStatus)
            .catch(console.error)
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        load();
        const iv = setInterval(load, 15000);
        return () => clearInterval(iv);
    }, []);

    const toggleAutopilot = async (action: 'start' | 'stop') => {
        setActing(true);
        try {
            await fetchAPI(`/api/autopilot/${action}?dry_run=true`, { method: 'POST' });
            setTimeout(load, 1000);
        } catch (e) { console.error(e); }
        finally { setActing(false); }
    };

    return (
        <div className="dashboard-layout">
            <Sidebar />
            <main className="main-content">
                <div className="page-header">
                    <div>
                        <h2>Autopilot Control</h2>
                        <div className="subtitle">Autonomous trading scheduler — all times ET</div>
                    </div>
                </div>

                {/* Status Card */}
                <div className="card" style={{ marginBottom: '24px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                            <div style={{
                                width: '48px', height: '48px', borderRadius: '50%',
                                background: status?.running ? 'var(--green-dim)' : 'var(--bg-elevated)',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                border: `2px solid ${status?.running ? 'var(--green)' : 'var(--border)'}`,
                            }}>
                                <span style={{ fontSize: '24px' }}>
                                    {status?.running ? '🟢' : '⚪'}
                                </span>
                            </div>
                            <div>
                                <div style={{ fontSize: '18px', fontWeight: 700 }}>
                                    {loading ? 'Checking...' : status?.running ? 'AUTOPILOT ACTIVE' : 'AUTOPILOT IDLE'}
                                </div>
                                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                                    Market: {status?.market_open ? '🟢 Open' : '🔴 Closed'} ·
                                    Scan every {status?.scan_interval || 15} min
                                </div>
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: '8px' }}>
                            {status?.running ? (
                                <button
                                    className="btn btn-danger"
                                    onClick={() => toggleAutopilot('stop')}
                                    disabled={acting}
                                >
                                    ⏹ Stop Autopilot
                                </button>
                            ) : (
                                <button
                                    className="btn btn-success"
                                    onClick={() => toggleAutopilot('start')}
                                    disabled={acting}
                                >
                                    ▶ Start Autopilot (Dry Run)
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* Schedule Timeline */}
                <div className="grid-2">
                    <div className="card">
                        <div className="card-header">
                            <h3>Daily Schedule</h3>
                        </div>
                        {[
                            { time: '09:25 AM', event: 'Pre-Open Data Refresh', icon: '📊' },
                            { time: '09:31 AM', event: 'Core Portfolio Rebalance', icon: '⚖️' },
                            { time: '09:31 AM', event: 'Leveraged ETF Deploy', icon: '⚡' },
                            { time: 'Every 15m', event: 'Intraday Scanner', icon: '🔍' },
                            { time: '03:55 PM', event: 'Leveraged EOD Cleanup', icon: '🧹' },
                            { time: '04:00 PM', event: 'Daily Summary Log', icon: '📝' },
                        ].map((item, i) => (
                            <div key={i} style={{
                                display: 'flex', alignItems: 'center', gap: '12px',
                                padding: '10px 0', borderBottom: i < 5 ? '1px solid var(--border)' : 'none',
                            }}>
                                <span style={{ fontSize: '18px' }}>{item.icon}</span>
                                <div>
                                    <div style={{ fontWeight: 600, fontSize: '13px' }}>{item.event}</div>
                                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.time} ET</div>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="card">
                        <div className="card-header">
                            <h3>Recent Events</h3>
                        </div>
                        <div style={{ maxHeight: '340px', overflow: 'auto' }}>
                            {status?.recent_events?.length > 0 ? (
                                status.recent_events.slice().reverse().map((e: any, i: number) => (
                                    <div key={i} style={{
                                        padding: '8px 0', borderBottom: '1px solid var(--border)',
                                        fontSize: '12px',
                                    }}>
                                        <span style={{ color: 'var(--text-muted)' }}>{e.timestamp}</span>
                                        <span style={{ marginLeft: '8px', color: 'var(--text-primary)' }}>{e.event}</span>
                                    </div>
                                ))
                            ) : (
                                <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '20px 0' }}>
                                    No events yet. Start the autopilot to begin trading.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
