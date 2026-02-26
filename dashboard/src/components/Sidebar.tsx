'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

const NAV_ITEMS = [
    { href: '/', label: 'Portfolio', icon: '📊' },
    { href: '/signals', label: 'Signals', icon: '📡' },
    { href: '/trades', label: 'Trade Center', icon: '💹' },
    { href: '/scanner', label: 'Scanner', icon: '🔍' },
    { href: '/autopilot', label: 'Autopilot', icon: '🤖' },
    { href: '/performance', label: 'Performance', icon: '📈' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
];

export default function Sidebar() {
    const pathname = usePathname();
    const [health, setHealth] = useState<any>(null);

    useEffect(() => {
        const check = async () => {
            try {
                const res = await fetch('/api/health');
                if (res.ok) setHealth(await res.json());
            } catch { setHealth(null); }
        };
        check();
        const iv = setInterval(check, 30000);
        return () => clearInterval(iv);
    }, []);

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <h1>HR Capital</h1>
                <span>Autonomous Trading System</span>
            </div>

            <nav className="sidebar-nav">
                {NAV_ITEMS.map(({ href, label, icon }) => (
                    <Link
                        key={href}
                        href={href}
                        className={pathname === href ? 'active' : ''}
                    >
                        <span style={{ fontSize: '16px' }}>{icon}</span>
                        {label}
                    </Link>
                ))}
            </nav>

            <div className="sidebar-status">
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <span className={`status-dot ${health ? 'live' : 'offline'}`} />
                    <span style={{ color: health ? 'var(--green)' : 'var(--text-muted)', fontWeight: 600 }}>
                        {health ? 'API Connected' : 'API Offline'}
                    </span>
                </div>
                {health && (
                    <div style={{ color: 'var(--text-muted)' }}>
                        Market: {health.market_open ? '🟢 Open' : '🔴 Closed'}
                        <br />
                        Autopilot: {health.autopilot ? '🟢 Running' : '⚪ Idle'}
                    </div>
                )}
            </div>
        </aside>
    );
}
