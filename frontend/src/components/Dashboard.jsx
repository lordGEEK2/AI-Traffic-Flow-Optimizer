import { useState, useEffect, useMemo } from 'react';

/**
 * Dashboard — Main analytics panel.
 * High-density data display: lane density table, vehicle counts,
 * density trend chart (canvas-based), system health, FPS stats.
 * No emojis. Government command center aesthetic.
 */
export default function Dashboard({ detection, density, systemHealth, videoSource }) {
    const [densityHistory, setDensityHistory] = useState([]);
    const lanes = density?.lanes || [];
    const vehicleTypes = detection?.vehicle_types || {};
    const totalVehicles = detection?.total_vehicles || 0;
    const fps = detection?.fps || 0;
    const overallDensity = density?.overall_density || 0;
    const overallLevel = density?.overall_level || 'low';
    const congestionIndex = density?.congestion_index || 0;

    // Collect density history for trend chart (last 60 ticks)
    useEffect(() => {
        if (overallDensity > 0 || densityHistory.length > 0) {
            setDensityHistory(prev => {
                const next = [...prev, { t: Date.now(), v: overallDensity }];
                return next.slice(-60);
            });
        }
    }, [overallDensity]);

    const levelColor = (level) => {
        const map = { low: 'text-status-green', medium: 'text-status-amber', high: 'text-status-red', critical: 'text-status-red' };
        return map[level] || 'text-text-secondary';
    };

    const levelBadge = (level) => {
        const map = { low: 'status-badge--green', medium: 'status-badge--amber', high: 'status-badge--red', critical: 'status-badge--red' };
        return map[level] || 'status-badge--green';
    };

    const densityBarColor = (level) => {
        const map = { low: '#22c55e', medium: '#f59e0b', high: '#ef4444', critical: '#ef4444' };
        return map[level] || '#22c55e';
    };

    const trendArrow = (trend) => {
        if (trend === 'increasing') return '\u2191';
        if (trend === 'decreasing') return '\u2193';
        return '\u2194';
    };

    return (
        <>
            {/* Row 1: Key Metrics */}
            <div className="grid grid-cols-5 gap-3">
                <MetricCard label="TOTAL VEHICLES" value={totalVehicles} />
                <MetricCard label="AVG DENSITY" value={`${overallDensity.toFixed(1)}%`} sublabel={overallLevel.toUpperCase()} sublabelClass={levelColor(overallLevel)} />
                <MetricCard label="CONGESTION INDEX" value={congestionIndex.toFixed(1)} sublabel={congestionIndex > 75 ? 'CRITICAL' : congestionIndex > 50 ? 'HIGH' : 'NORMAL'} sublabelClass={congestionIndex > 75 ? 'text-status-red' : congestionIndex > 50 ? 'text-status-amber' : 'text-status-green'} />
                <MetricCard label="FRAME RATE" value={`${fps.toFixed(1)}`} sublabel="FPS" />
                <MetricCard label="UPTIME" value={formatUptime(systemHealth?.uptime_seconds)} sublabel={systemHealth?.status?.toUpperCase() || 'UNKNOWN'} sublabelClass={systemHealth?.status === 'operational' ? 'text-status-green' : 'text-status-amber'} />
            </div>

            {/* Row 2: Lane Density Table + Vehicle Types */}
            <div className="grid grid-cols-3 gap-3">
                {/* Lane Density Table (2 cols) */}
                <div className="col-span-2 panel">
                    <div className="panel-header">Lane-Wise Density Analysis</div>
                    <div className="p-2">
                        <table className="data-table">
                            <thead>
                                <tr>
                                    <th>Lane</th>
                                    <th>Vehicles</th>
                                    <th>Density</th>
                                    <th style={{ width: '30%' }}>Level</th>
                                    <th>Trend</th>
                                    <th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {lanes.length > 0 ? lanes.map(lane => (
                                    <tr key={lane.lane_id}>
                                        <td className="font-semibold text-text-heading">{lane.lane_id}</td>
                                        <td>{lane.vehicle_count}</td>
                                        <td>
                                            <div className="flex items-center gap-2">
                                                <span className="w-10 text-right">{lane.smoothed_density?.toFixed(1) || lane.raw_density?.toFixed(1) || '0.0'}%</span>
                                                <div className="density-bar flex-1">
                                                    <div
                                                        className="density-bar__fill"
                                                        style={{
                                                            width: `${Math.min(100, lane.smoothed_density || lane.raw_density || 0)}%`,
                                                            backgroundColor: densityBarColor(lane.level),
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        </td>
                                        <td>
                                            <span className={`status-badge ${levelBadge(lane.level)}`}>
                                                {lane.level?.toUpperCase()}
                                            </span>
                                        </td>
                                        <td className="text-center">
                                            <span className={lane.trend === 'increasing' ? 'text-status-red' : lane.trend === 'decreasing' ? 'text-status-green' : 'text-text-muted'}>
                                                {trendArrow(lane.trend)}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`status-dot ${lane.level === 'critical' ? 'status-dot--red' : lane.level === 'high' ? 'status-dot--amber' : 'status-dot--green'}`}></span>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan={6} className="text-center text-text-muted py-4">Awaiting data...</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Vehicle Type Breakdown */}
                <div className="panel">
                    <div className="panel-header">Vehicle Classification</div>
                    <div className="p-3 space-y-3">
                        {Object.entries(vehicleTypes).map(([type, count]) => (
                            <div key={type} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: typeColor(type) }}></div>
                                    <span className="text-xs text-text-secondary uppercase">{type}</span>
                                </div>
                                <span className="font-mono text-sm text-text-heading font-medium">{count}</span>
                            </div>
                        ))}
                        {Object.keys(vehicleTypes).length === 0 && (
                            <div className="text-xs text-text-muted text-center py-4">No detections</div>
                        )}
                        <div className="pt-2 border-t border-panel-border flex items-center justify-between">
                            <span className="text-xs text-text-secondary font-semibold">TOTAL</span>
                            <span className="font-mono text-lg text-text-heading font-semibold">{totalVehicles}</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* Row 3: Density Trend + System Health */}
            <div className="grid grid-cols-3 gap-3">
                {/* Density Trend Chart */}
                <div className="col-span-2 panel">
                    <div className="panel-header">Density Trend (60-Tick Window)</div>
                    <div className="p-2">
                        <DensityChart data={densityHistory} />
                    </div>
                </div>

                {/* System Health */}
                <div className="panel">
                    <div className="panel-header">System Health</div>
                    <div className="p-3 space-y-2">
                        <HealthRow label="Video Source" value={videoSource?.mode?.toUpperCase() || 'SIM'} ok={videoSource?.healthy} />
                        <HealthRow label="Camera Feed" value={videoSource?.healthy ? 'ACTIVE' : 'OFFLINE'} ok={videoSource?.healthy} />
                        <HealthRow label="Database" value={systemHealth?.database_connected ? 'CONNECTED' : 'DISCONNECTED'} ok={systemHealth?.database_connected} />
                        <HealthRow label="Processing" value={systemHealth?.status?.toUpperCase() || 'UNKNOWN'} ok={systemHealth?.status === 'operational'} />
                        <HealthRow label="WS Clients" value={systemHealth?.active_connections || 0} ok={true} />
                        <div className="pt-2 border-t border-panel-border text-2xs font-mono text-text-muted space-y-1">
                            <div className="flex justify-between">
                                <span>Frames Read</span>
                                <span>{videoSource?.frames_read || 0}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Frames Dropped</span>
                                <span className={videoSource?.frames_dropped > 0 ? 'text-status-amber' : ''}>{videoSource?.frames_dropped || 0}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Reconnections</span>
                                <span className={videoSource?.reconnections > 0 ? 'text-status-red' : ''}>{videoSource?.reconnections || 0}</span>
                            </div>
                            <div className="flex justify-between">
                                <span>Tick Count</span>
                                <span>{systemHealth?.tick_count || 0}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

/* --- Sub-Components --- */

function MetricCard({ label, value, sublabel, sublabelClass }) {
    return (
        <div className="panel p-3">
            <div className="text-2xs text-text-muted font-semibold uppercase tracking-wider mb-1">{label}</div>
            <div className="font-mono text-xl font-semibold text-text-heading">{value}</div>
            {sublabel && <div className={`text-2xs font-mono mt-0.5 ${sublabelClass || 'text-text-muted'}`}>{sublabel}</div>}
        </div>
    );
}

function HealthRow({ label, value, ok }) {
    return (
        <div className="flex items-center justify-between text-xs">
            <span className="text-text-secondary">{label}</span>
            <div className="flex items-center gap-1.5">
                <span className={`status-dot ${ok ? 'status-dot--green' : 'status-dot--red'}`}></span>
                <span className="font-mono text-2xs">{value}</span>
            </div>
        </div>
    );
}

function DensityChart({ data }) {
    if (data.length < 2) {
        return <div className="h-24 flex items-center justify-center text-text-muted text-xs">Collecting data...</div>;
    }

    const height = 96;
    const width = 100; // percentage
    const max = Math.max(...data.map(d => d.v), 100);
    const points = data.map((d, i) => {
        const x = (i / (data.length - 1)) * 100;
        const y = height - (d.v / max) * height;
        return `${x},${y}`;
    }).join(' ');

    // Thresholds
    const thresh25 = height - (25 / max) * height;
    const thresh50 = height - (50 / max) * height;
    const thresh75 = height - (75 / max) * height;

    return (
        <svg viewBox={`0 0 100 ${height}`} className="w-full h-24" preserveAspectRatio="none">
            {/* Threshold lines */}
            <line x1="0" y1={thresh75} x2="100" y2={thresh75} stroke="#ef4444" strokeWidth="0.3" strokeDasharray="2,2" opacity="0.4" />
            <line x1="0" y1={thresh50} x2="100" y2={thresh50} stroke="#f59e0b" strokeWidth="0.3" strokeDasharray="2,2" opacity="0.4" />
            <line x1="0" y1={thresh25} x2="100" y2={thresh25} stroke="#22c55e" strokeWidth="0.3" strokeDasharray="2,2" opacity="0.4" />
            {/* Fill area */}
            <polygon
                points={`0,${height} ${points} 100,${height}`}
                fill="rgba(59,130,246,0.1)"
            />
            {/* Line */}
            <polyline
                points={points}
                fill="none"
                stroke="#3b82f6"
                strokeWidth="0.8"
            />
        </svg>
    );
}

/* --- Utilities --- */

function typeColor(type) {
    const map = { car: '#3b82f6', truck: '#f59e0b', bus: '#22c55e', motorcycle: '#a855f7' };
    return map[type] || '#6b7280';
}

function formatUptime(seconds) {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
}
