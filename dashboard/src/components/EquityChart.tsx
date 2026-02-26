'use client';

import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { fetchAPI } from '@/lib/api';

const PERIODS = ['1D', '1W', '1M', '3M', '1Y', 'ALL'] as const;
type Period = (typeof PERIODS)[number];

interface DataPoint {
    time: number;
    equity: number;
    pnl: number | null;
    pnl_pct: number | null;
}

interface HistoryData {
    period: string;
    points: DataPoint[];
    summary: {
        start: number;
        end: number;
        high: number;
        low: number;
        change: number;
        change_pct: number;
    };
}

// ── TradingView-style colors ──
const COLORS = {
    green: '#059669',
    greenDim: 'rgba(5, 150, 105, 0.08)',
    greenGlow: 'rgba(5, 150, 105, 0.2)',
    red: '#DC2626',
    redDim: 'rgba(220, 38, 38, 0.08)',
    redGlow: 'rgba(220, 38, 38, 0.2)',
    grid: 'rgba(0, 0, 0, 0.06)',
    gridLabel: 'rgba(0, 0, 0, 0.35)',
    crosshair: 'rgba(0, 0, 0, 0.15)',
    tooltip: 'rgba(255, 255, 255, 0.95)',
    tooltipBorder: 'rgba(0, 0, 0, 0.08)',
};

function formatTime(ts: number, period: Period): string {
    const d = new Date(ts * 1000);
    if (period === '1D') return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    if (period === '1W') return d.toLocaleDateString('en-US', { weekday: 'short', hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatDollar(val: number): string {
    return '$' + val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function EquityChart() {
    const [period, setPeriod] = useState<Period>('1D');
    const [data, setData] = useState<HistoryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [hover, setHover] = useState<DataPoint | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const animFrameRef = useRef<number>(0);

    const fetchData = useCallback(async (p: Period) => {
        setLoading(true);
        try {
            const result = await fetchAPI(`/api/portfolio/history?period=${p}`);
            setData(result);
        } catch (e) {
            console.error('Failed to fetch chart data', e);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        fetchData(period);
        // Auto-refresh: 1 minute for 1D, 5 minutes for 1W, else no auto-refresh
        const interval = period === '1D' ? 60000 : period === '1W' ? 300000 : 0;
        if (interval > 0) {
            const timer = setInterval(() => fetchData(period), interval);
            return () => clearInterval(timer);
        }
    }, [period, fetchData]);

    const isPositive = (data?.summary?.change ?? 0) >= 0;
    const lineColor = isPositive ? COLORS.green : COLORS.red;
    const fillColor = isPositive ? COLORS.greenDim : COLORS.redDim;
    const glowColor = isPositive ? COLORS.greenGlow : COLORS.redGlow;

    // ── Canvas rendering ──
    useEffect(() => {
        if (!data?.points?.length || !canvasRef.current || !containerRef.current) return;

        const canvas = canvasRef.current;
        const container = containerRef.current;
        const dpr = window.devicePixelRatio || 1;
        const rect = container.getBoundingClientRect();
        const W = rect.width;
        const H = rect.height;

        canvas.width = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width = `${W}px`;
        canvas.style.height = `${H}px`;

        const ctx = canvas.getContext('2d')!;
        ctx.scale(dpr, dpr);

        const points = data.points;
        const padding = { top: 12, right: 60, bottom: 28, left: 12 };
        const chartW = W - padding.left - padding.right;
        const chartH = H - padding.top - padding.bottom;

        const minE = Math.min(...points.map(p => p.equity));
        const maxE = Math.max(...points.map(p => p.equity));
        const range = maxE - minE || 1;
        const buffer = range * 0.05;

        const scaleX = (i: number) => padding.left + (i / (points.length - 1)) * chartW;
        const scaleY = (v: number) => padding.top + chartH - ((v - (minE - buffer)) / (range + buffer * 2)) * chartH;

        // Clear
        ctx.clearRect(0, 0, W, H);

        // ── Grid lines ──
        const gridLines = 5;
        ctx.strokeStyle = COLORS.grid;
        ctx.lineWidth = 1;
        ctx.setLineDash([]);
        ctx.font = '10px Inter, monospace';
        ctx.fillStyle = COLORS.gridLabel;
        ctx.textAlign = 'right';

        for (let i = 0; i <= gridLines; i++) {
            const val = minE - buffer + ((range + buffer * 2) / gridLines) * i;
            const y = scaleY(val);
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(W - padding.right, y);
            ctx.stroke();
            ctx.fillText(formatDollar(val), W - 4, y + 3);
        }

        // ── Time labels ──
        ctx.textAlign = 'center';
        ctx.fillStyle = COLORS.gridLabel;
        const labelCount = Math.min(6, points.length);
        for (let i = 0; i < labelCount; i++) {
            const idx = Math.round((i / (labelCount - 1)) * (points.length - 1));
            const x = scaleX(idx);
            const label = formatTime(points[idx].time, period);
            ctx.fillText(label, x, H - 6);
        }

        // ── Gradient fill ──
        const gradient = ctx.createLinearGradient(0, scaleY(maxE), 0, scaleY(minE - buffer));
        gradient.addColorStop(0, lineColor.replace(')', ', 0.25)').replace('rgb', 'rgba'));
        gradient.addColorStop(1, 'transparent');

        ctx.beginPath();
        ctx.moveTo(scaleX(0), scaleY(minE - buffer));
        for (let i = 0; i < points.length; i++) {
            ctx.lineTo(scaleX(i), scaleY(points[i].equity));
        }
        ctx.lineTo(scaleX(points.length - 1), scaleY(minE - buffer));
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // ── Line ──
        ctx.beginPath();
        ctx.moveTo(scaleX(0), scaleY(points[0].equity));
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(scaleX(i), scaleY(points[i].equity));
        }
        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        ctx.setLineDash([]);
        ctx.stroke();

        // ── Glow effect ──
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = 8;
        ctx.stroke();
        ctx.shadowBlur = 0;

        // ── Store scale functions for hover ──
        (canvas as any)._chartMeta = { points, scaleX, scaleY, padding, chartW, chartH, W, H };

    }, [data, lineColor, fillColor, glowColor, period]);

    // ── Mouse hover → crosshair + tooltip ──
    const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas || !(canvas as any)._chartMeta) return;
        const { points, scaleX, padding, chartW } = (canvas as any)._chartMeta;
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;

        const idx = Math.round(((mouseX - padding.left) / chartW) * (points.length - 1));
        const clamped = Math.max(0, Math.min(points.length - 1, idx));
        setHover(points[clamped]);
    }, []);

    const displayPoint = hover || (data?.points?.length ? data.points[data.points.length - 1] : null);
    const displayChange = displayPoint && data
        ? displayPoint.equity - data.summary.start
        : data?.summary?.change ?? 0;
    const displayChangePct = displayPoint && data?.summary?.start
        ? (displayChange / data.summary.start) * 100
        : data?.summary?.change_pct ?? 0;

    return (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            {/* Header bar */}
            <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                padding: '16px 20px 8px',
            }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
                        <span style={{
                            fontSize: '28px', fontWeight: 800, fontFamily: 'var(--font-mono)',
                            letterSpacing: '-1px',
                        }}>
                            {displayPoint ? formatDollar(displayPoint.equity) : loading ? '—' : formatDollar(data?.summary?.end ?? 0)}
                        </span>
                        <span style={{
                            fontSize: '14px', fontWeight: 600,
                            color: displayChange >= 0 ? COLORS.green : COLORS.red,
                        }}>
                            {displayChange >= 0 ? '+' : ''}{formatDollar(displayChange)}
                            {' '}
                            ({displayChangePct >= 0 ? '+' : ''}{displayChangePct.toFixed(2)}%)
                        </span>
                    </div>
                    {displayPoint && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {formatTime(displayPoint.time, period)}
                        </div>
                    )}
                </div>

                {/* Period selector */}
                <div style={{
                    display: 'flex', gap: '2px', background: 'var(--bg-elevated)',
                    borderRadius: 'var(--radius-sm)', padding: '2px',
                }}>
                    {PERIODS.map(p => (
                        <button
                            key={p}
                            onClick={() => { setPeriod(p); setHover(null); }}
                            style={{
                                padding: '4px 10px', fontSize: '11px', fontWeight: 700,
                                border: 'none', borderRadius: '4px', cursor: 'pointer',
                                transition: 'all 0.15s',
                                background: period === p ? (isPositive ? COLORS.green : COLORS.red) : 'transparent',
                                color: period === p ? '#fff' : 'var(--text-muted)',
                            }}
                        >
                            {p}
                        </button>
                    ))}
                </div>
            </div>

            {/* Chart area */}
            <div
                ref={containerRef}
                style={{
                    position: 'relative', height: '300px', padding: '0 0 0 0',
                    cursor: 'crosshair',
                }}
            >
                {loading ? (
                    <div style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        height: '100%', color: 'var(--text-muted)', fontSize: '13px',
                    }}>
                        <div className="spinner" style={{ marginRight: '8px' }} /> Loading chart...
                    </div>
                ) : (
                    <canvas
                        ref={canvasRef}
                        style={{ width: '100%', height: '100%' }}
                        onMouseMove={handleMouseMove}
                        onMouseLeave={() => setHover(null)}
                    />
                )}
            </div>

            {/* Bottom stats bar */}
            {data?.summary && !loading && (
                <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    padding: '8px 20px 12px', borderTop: `1px solid ${COLORS.grid}`,
                    fontSize: '11px', color: 'var(--text-muted)',
                }}>
                    <span>O <b style={{ color: 'var(--text-primary)' }}>{formatDollar(data.summary.start)}</b></span>
                    <span>H <b style={{ color: COLORS.green }}>{formatDollar(data.summary.high)}</b></span>
                    <span>L <b style={{ color: COLORS.red }}>{formatDollar(data.summary.low)}</b></span>
                    <span>C <b style={{ color: 'var(--text-primary)' }}>{formatDollar(data.summary.end)}</b></span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px' }}>
                        {data.points.length} pts · auto-refresh {period === '1D' ? '1m' : period === '1W' ? '5m' : 'off'}
                    </span>
                </div>
            )}
        </div>
    );
}
