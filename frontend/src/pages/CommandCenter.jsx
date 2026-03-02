import { useState, useEffect, useMemo } from 'react';
import EmergencyAlert from '../components/EmergencyAlert';
import SignalPanel from '../components/SignalPanel';
import TrafficView from '../components/TrafficView';

/**
 * CommandCenter -- Main operational dashboard (Page 1).
 * Shows live feed status, signal state, density heat, emergency banner,
 * intersection health score, AI reasoning panel, and system health.
 */
export default function CommandCenter({ data, connected, sendCommand }) {
    const [densityHistory, setDensityHistory] = useState([]);

    const detection = data?.detection || {};
    const density = data?.density || {};
    const intersection = data?.intersection || {};
    const corridor = data?.corridor || {};
    const videoSource = data?.video_source || {};
    const systemHealth = data?.system_health || {};
    const alerts = data?.alerts || [];
    const analytics = data?.analytics || {};
    const violations = data?.violations || {};
    const weather = intersection.weather || 'clear';

    const totalVehicles = detection?.total_vehicles || 0;
    const fps = detection?.fps || 0;
    const overallDensity = density?.overall_density || 0;
    const overallLevel = density?.overall_level || 'low';
    const congestionIndex = density?.congestion_index || 0;
    const healthScore = analytics?.health?.intersection_health_score ?? '--';
    const signalEfficiency = analytics?.health?.signal_efficiency ?? '--';
    const vpm = analytics?.flow?.vehicles_per_minute ?? '--';
    const avgWait = analytics?.health?.avg_wait_time_seconds ?? '--';
    const forecast = analytics?.forecast || {};
    const aiReasons = analytics?.ai_reasons || [];
    const vehicleTypes = detection?.vehicle_types || {};
    const lanes = density?.lanes || [];

    useEffect(() => {
        if (overallDensity > 0 || densityHistory.length > 0) {
            setDensityHistory(prev => [...prev, { t: Date.now(), v: overallDensity }].slice(-60));
        }
    }, [overallDensity]);

    const levelColor = (l) => ({ low: 'text-status-green', medium: 'text-status-amber', high: 'text-status-red', critical: 'text-status-red' }[l] || 'text-text-secondary');
    const levelBadge = (l) => ({ low: 'status-badge--green', medium: 'status-badge--amber', high: 'status-badge--red', critical: 'status-badge--red' }[l] || 'status-badge--green');
    const densityBarColor = (l) => ({ low: '#22c55e', medium: '#f59e0b', high: '#ef4444', critical: '#ef4444' }[l] || '#22c55e');
    const trendArrow = (t) => t === 'increasing' ? '\u2191' : t === 'decreasing' ? '\u2193' : '\u2194';
    const typeColor = (t) => ({ person: '#06b6d4', car: '#3b82f6', truck: '#f59e0b', bus: '#22c55e', motorcycle: '#a855f7', auto_rickshaw: '#ec4899', e_rickshaw: '#14b8a6' }[t] || '#6b7280');

    const healthColor = (s) => {
        if (typeof s !== 'number') return 'text-text-muted';
        if (s >= 70) return 'text-status-green';
        if (s >= 40) return 'text-status-amber';
        return 'text-status-red';
    };

    return (
        <div className="p-3 space-y-3">
            {/* Header Bar */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-sm font-bold text-text-heading uppercase tracking-wider">Command Center</h2>
                    <span className="text-2xs text-text-muted font-mono">ITO Intersection, Delhi</span>
                    <span className={`text-2xs font-bold ${weather === 'rain' ? 'text-status-blue' : 'text-status-green'}`}>
                        {weather === 'rain' ? 'RAIN (+2s RED)' : 'CLEAR'}
                    </span>
                </div>
                <div className={`status-badge ${connected ? 'status-badge--green' : 'status-badge--red'}`}>
                    <span className={`status-dot ${connected ? 'status-dot--green' : 'status-dot--red'}`}></span>
                    {connected ? 'LIVE' : 'OFFLINE'}
                </div>
            </div>

            {/* Emergency Alert */}
            {corridor.active && (
                <EmergencyAlert corridor={corridor} alerts={alerts} onClear={() => sendCommand({ action: 'clear_emergency' })} />
            )}

            {/* Row 1: Key Metrics + Health Score */}
            <div className="grid grid-cols-6 gap-3">
                <MetricCard label="TOTAL VEHICLES" value={totalVehicles} />
                <MetricCard label="VEHICLES / MIN" value={typeof vpm === 'number' ? vpm.toFixed(1) : vpm} />
                <MetricCard label="AVG DENSITY" value={`${overallDensity.toFixed(1)}%`} sublabel={overallLevel.toUpperCase()} sublabelClass={levelColor(overallLevel)} />
                <MetricCard label="SIGNAL EFF." value={typeof signalEfficiency === 'number' ? `${signalEfficiency.toFixed(0)}%` : signalEfficiency} />
                <MetricCard label="AVG WAIT" value={typeof avgWait === 'number' ? `${avgWait.toFixed(0)}s` : avgWait} />
                <div className="panel p-3 text-center">
                    <div className="text-2xs text-text-muted font-semibold uppercase tracking-wider mb-1">HEALTH SCORE</div>
                    <div className={`font-mono text-3xl font-bold ${healthColor(healthScore)}`}>{typeof healthScore === 'number' ? healthScore : '--'}</div>
                    <div className="text-2xs text-text-muted">/100</div>
                </div>
            </div>

            {/* Row 2: Main Grid */}
            <div className="grid grid-cols-12 gap-3">
                {/* Left: Lane Table + Vehicle Types */}
                <div className="col-span-5 space-y-3">
                    <div className="panel">
                        <div className="panel-header">Lane-Wise Density</div>
                        <div className="p-2">
                            <table className="data-table">
                                <thead><tr><th>Lane</th><th>Count</th><th>Density</th><th>Level</th><th>Trend</th></tr></thead>
                                <tbody>
                                    {lanes.length > 0 ? lanes.map(lane => (
                                        <tr key={lane.lane_id}>
                                            <td className="font-semibold text-text-heading">{lane.lane_id}</td>
                                            <td>{lane.vehicle_count}</td>
                                            <td>
                                                <div className="flex items-center gap-1">
                                                    <span className="w-8 text-right text-2xs">{(lane.smoothed_density || 0).toFixed(0)}%</span>
                                                    <div className="density-bar flex-1"><div className="density-bar__fill" style={{ width: `${Math.min(100, lane.smoothed_density || 0)}%`, backgroundColor: densityBarColor(lane.level) }} /></div>
                                                </div>
                                            </td>
                                            <td><span className={`status-badge ${levelBadge(lane.level)}`}>{lane.level?.toUpperCase()}</span></td>
                                            <td className="text-center"><span className={lane.trend === 'increasing' ? 'text-status-red' : lane.trend === 'decreasing' ? 'text-status-green' : 'text-text-muted'}>{trendArrow(lane.trend)}</span></td>
                                        </tr>
                                    )) : <tr><td colSpan={5} className="text-center text-text-muted py-4">Awaiting data...</td></tr>}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <div className="panel">
                        <div className="panel-header">Vehicle Classification (Delhi Mix)</div>
                        <div className="p-3 grid grid-cols-2 gap-2">
                            {Object.entries(vehicleTypes).map(([type, count]) => (
                                <div key={type} className="flex items-center justify-between">
                                    <div className="flex items-center gap-1.5">
                                        <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: typeColor(type) }}></div>
                                        <span className="text-2xs text-text-secondary uppercase">{type.replace('_', ' ')}</span>
                                    </div>
                                    <span className="font-mono text-xs text-text-heading font-medium">{count}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Center: Signal + Map */}
                <div className="col-span-4 space-y-3">
                    <SignalPanel
                        intersection={intersection} corridor={corridor} density={density}
                        onTriggerEmergency={(dir) => sendCommand({ action: 'trigger_emergency', direction: dir, vehicle_type: 'ambulance' })}
                        onClearEmergency={() => sendCommand({ action: 'clear_emergency' })}
                    />
                    <TrafficView intersection={intersection} density={density} corridor={corridor} />
                </div>

                {/* Right: AI Reasoning + Forecast */}
                <div className="col-span-3 space-y-3">
                    {/* AI Reasoning Panel */}
                    <div className="panel">
                        <div className="panel-header">AI Decision Log</div>
                        <div className="p-2 space-y-1.5 max-h-48 overflow-auto">
                            {aiReasons.length > 0 ? aiReasons.map((r, i) => (
                                <div key={i} className={`text-2xs p-1.5 rounded border-l-2 ${r.severity === 'critical' ? 'border-status-red bg-status-red/5 text-status-red' :
                                        r.severity === 'warning' ? 'border-status-amber bg-status-amber/5 text-status-amber' :
                                            r.severity === 'high' ? 'border-status-red bg-status-red/5 text-status-red' :
                                                'border-status-blue bg-status-blue/5 text-status-blue'
                                    }`}>
                                    <div className="font-semibold uppercase text-2xs mb-0.5">{r.type}</div>
                                    <div className="text-text-secondary">{r.message}</div>
                                </div>
                            )) : <div className="text-2xs text-text-muted text-center py-4">No active AI decisions</div>}
                        </div>
                    </div>

                    {/* Forecast */}
                    <div className="panel">
                        <div className="panel-header">5-Min Forecast</div>
                        <div className="p-3 space-y-2">
                            <div className="flex justify-between text-xs">
                                <span className="text-text-secondary">Predicted Density</span>
                                <span className="font-mono font-semibold">{forecast.predicted_density?.toFixed(1) || '--'}%</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-text-secondary">Trend</span>
                                <span className={`font-mono font-semibold ${forecast.trend === 'rising' ? 'text-status-red' : forecast.trend === 'falling' ? 'text-status-green' : 'text-text-muted'}`}>{forecast.trend?.toUpperCase() || '--'}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-text-secondary">Warning</span>
                                <span className={`font-mono text-2xs ${forecast.warning?.includes('critical') ? 'text-status-red' : forecast.warning?.includes('high') ? 'text-status-amber' : 'text-status-green'}`}>{forecast.warning?.replace(/_/g, ' ').toUpperCase() || 'NONE'}</span>
                            </div>
                            <div className="flex justify-between text-xs">
                                <span className="text-text-secondary">Confidence</span>
                                <span className="font-mono">{((forecast.confidence || 0) * 100).toFixed(0)}%</span>
                            </div>
                        </div>
                    </div>

                    {/* Violations Summary */}
                    <div className="panel">
                        <div className="panel-header">Violations Detected</div>
                        <div className="p-3">
                            <div className="text-2xl font-mono font-bold text-status-red">{violations?.summary?.total_violations || 0}</div>
                            <div className="text-2xs text-text-muted mt-1 space-y-0.5">
                                {Object.entries(violations?.summary?.by_type || {}).map(([t, c]) => (
                                    <div key={t} className="flex justify-between">
                                        <span>{t.replace('_', ' ')}</span>
                                        <span className="font-mono">{c}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Row 3: Density Trend */}
            <div className="panel">
                <div className="panel-header">Density Trend (60-Tick Window)</div>
                <div className="p-2"><DensityChart data={densityHistory} /></div>
            </div>
        </div>
    );
}

function MetricCard({ label, value, sublabel, sublabelClass }) {
    return (
        <div className="panel p-3">
            <div className="text-2xs text-text-muted font-semibold uppercase tracking-wider mb-1">{label}</div>
            <div className="font-mono text-xl font-semibold text-text-heading">{value}</div>
            {sublabel && <div className={`text-2xs font-mono mt-0.5 ${sublabelClass || 'text-text-muted'}`}>{sublabel}</div>}
        </div>
    );
}

function DensityChart({ data }) {
    if (data.length < 2) return <div className="h-20 flex items-center justify-center text-text-muted text-xs">Collecting data...</div>;
    const height = 80, max = Math.max(...data.map(d => d.v), 100);
    const points = data.map((d, i) => `${(i / (data.length - 1)) * 100},${height - (d.v / max) * height}`).join(' ');
    return (
        <svg viewBox={`0 0 100 ${height}`} className="w-full h-20" preserveAspectRatio="none">
            <line x1="0" y1={height - (75 / max) * height} x2="100" y2={height - (75 / max) * height} stroke="#ef4444" strokeWidth="0.3" strokeDasharray="2,2" opacity="0.4" />
            <line x1="0" y1={height - (50 / max) * height} x2="100" y2={height - (50 / max) * height} stroke="#f59e0b" strokeWidth="0.3" strokeDasharray="2,2" opacity="0.4" />
            <polygon points={`0,${height} ${points} 100,${height}`} fill="rgba(59,130,246,0.1)" />
            <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="0.8" />
        </svg>
    );
}
