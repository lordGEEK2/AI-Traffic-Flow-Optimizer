import { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, PieChart, Pie, Cell } from 'recharts';

/**
 * AnalyticsPage -- Intersection Analytics (Page 4).
 * Shows Recharts graphs: hourly traffic, lane utilization, congestion trend, signal efficiency.
 */
export default function AnalyticsPage({ data }) {
    const [history, setHistory] = useState([]);
    const [healthHistory, setHealthHistory] = useState([]);

    const analytics = data?.analytics || {};
    const flow = analytics?.flow || {};
    const health = analytics?.health || {};
    const trends = analytics?.trends || {};

    // Collect live analytics history
    useEffect(() => {
        if (health.intersection_health_score != null) {
            const entry = {
                time: new Date().toLocaleTimeString('en-IN', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }),
                health: health.intersection_health_score,
                efficiency: health.signal_efficiency || 50,
                density: data?.density?.overall_density || 0,
                vehicles: data?.detection?.total_vehicles || 0,
                wait: health.avg_wait_time_seconds || 0,
            };
            setHistory(prev => [...prev, entry].slice(-30));
            setHealthHistory(prev => [...prev, entry].slice(-30));
        }
    }, [data?.timestamp]);

    // Lane utilization for bar chart
    const laneUtilization = Object.entries(flow.per_lane_utilization || {}).map(([lane, val]) => ({
        lane, utilization: val,
        throughput: flow.per_lane_throughput?.[lane] || 0,
    }));

    // Vehicle type distribution for pie chart
    const vehicleTypes = Object.entries(data?.detection?.vehicle_types || {}).filter(([, c]) => c > 0).map(([type, count]) => ({ name: type.replace('_', ' '), value: count }));
    const PIE_COLORS = ['#06b6d4', '#3b82f6', '#f59e0b', '#22c55e', '#a855f7', '#ec4899', '#14b8a6'];

    return (
        <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-text-heading uppercase tracking-wider">Intersection Analytics</h2>
                <span className="text-2xs text-text-muted font-mono">ITO-INT-001 | {trends.is_peak_hour ? 'PEAK HOUR' : 'Normal Hours'}</span>
            </div>

            {/* Summary Row */}
            <div className="grid grid-cols-5 gap-3">
                <SummaryCard label="Health Score" value={health.intersection_health_score ?? '--'} unit="/100" color={health.intersection_health_score >= 70 ? 'text-status-green' : health.intersection_health_score >= 40 ? 'text-status-amber' : 'text-status-red'} />
                <SummaryCard label="Signal Efficiency" value={health.signal_efficiency?.toFixed?.(0) ?? '--'} unit="%" />
                <SummaryCard label="Vehicles/Min" value={flow.vehicles_per_minute?.toFixed?.(1) ?? '--'} />
                <SummaryCard label="Avg Wait" value={health.avg_wait_time_seconds?.toFixed?.(0) ?? '--'} unit="s" />
                <SummaryCard label="Congestion" value={trends.congestion_trend?.toUpperCase() ?? '--'} color={trends.congestion_trend === 'rising' ? 'text-status-red' : trends.congestion_trend === 'falling' ? 'text-status-green' : 'text-text-muted'} />
            </div>

            {/* Charts Row 1 */}
            <div className="grid grid-cols-2 gap-3">
                {/* Health & Efficiency Trend */}
                <div className="panel">
                    <div className="panel-header">Health Score & Signal Efficiency Trend</div>
                    <div className="p-2" style={{ height: 220 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={healthHistory}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#64748b' }} />
                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
                                <Line type="monotone" dataKey="health" stroke="#22c55e" strokeWidth={2} dot={false} name="Health" />
                                <Line type="monotone" dataKey="efficiency" stroke="#3b82f6" strokeWidth={2} dot={false} name="Efficiency" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Lane Utilization Bar */}
                <div className="panel">
                    <div className="panel-header">Lane Utilization (%)</div>
                    <div className="p-2" style={{ height: 220 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={laneUtilization}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                <XAxis dataKey="lane" tick={{ fontSize: 10, fill: '#64748b' }} />
                                <YAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#64748b' }} />
                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
                                <Bar dataKey="utilization" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </div>

            {/* Charts Row 2 */}
            <div className="grid grid-cols-2 gap-3">
                {/* Congestion Trend */}
                <div className="panel">
                    <div className="panel-header">Density & Wait Time Trend</div>
                    <div className="p-2" style={{ height: 220 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={history}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#64748b' }} interval="preserveStartEnd" />
                                <YAxis tick={{ fontSize: 9, fill: '#64748b' }} />
                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
                                <Line type="monotone" dataKey="density" stroke="#ef4444" strokeWidth={2} dot={false} name="Density %" />
                                <Line type="monotone" dataKey="wait" stroke="#f59e0b" strokeWidth={2} dot={false} name="Wait (s)" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Vehicle Distribution Pie */}
                <div className="panel">
                    <div className="panel-header">Vehicle Type Distribution (Delhi Mix)</div>
                    <div className="p-2 flex items-center" style={{ height: 220 }}>
                        <ResponsiveContainer width="60%" height="100%">
                            <PieChart>
                                <Pie data={vehicleTypes} cx="50%" cy="50%" outerRadius={80} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false} fontSize={9}>
                                    {vehicleTypes.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                                </Pie>
                                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', fontSize: 11 }} />
                            </PieChart>
                        </ResponsiveContainer>
                        <div className="flex-1 space-y-1">
                            {vehicleTypes.map((vt, i) => (
                                <div key={vt.name} className="flex items-center gap-1.5 text-2xs">
                                    <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                                    <span className="text-text-secondary">{vt.name}</span>
                                    <span className="font-mono ml-auto">{vt.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function SummaryCard({ label, value, unit, color }) {
    return (
        <div className="panel p-3">
            <div className="text-2xs text-text-muted font-semibold uppercase tracking-wider mb-1">{label}</div>
            <div className={`font-mono text-xl font-semibold ${color || 'text-text-heading'}`}>{value}{unit && <span className="text-xs text-text-muted ml-0.5">{unit}</span>}</div>
        </div>
    );
}
