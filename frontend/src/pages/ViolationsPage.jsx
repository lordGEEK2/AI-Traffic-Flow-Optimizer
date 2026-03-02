import { useState, useEffect } from 'react';

/**
 * ViolationsPage -- Traffic Violations Monitor (Page 3).
 * Shows violation table with filters by type, time, and lane.
 */
export default function ViolationsPage({ data }) {
    const [violations, setViolations] = useState([]);
    const [filterType, setFilterType] = useState('all');
    const [filterLane, setFilterLane] = useState('all');

    // Fetch violations from API
    useEffect(() => {
        const fetchViolations = async () => {
            try {
                const res = await fetch('http://localhost:8000/api/violations/recent?limit=100');
                const data = await res.json();
                if (Array.isArray(data)) setViolations(data);
            } catch { /* silent */ }
        };
        fetchViolations();
        const interval = setInterval(fetchViolations, 5000);
        return () => clearInterval(interval);
    }, []);

    // Also collect live violations from WebSocket
    useEffect(() => {
        const newViolations = data?.violations?.recent || [];
        if (newViolations.length > 0) {
            setViolations(prev => [...newViolations, ...prev].slice(0, 200));
        }
    }, [data?.violations?.recent]);

    const summary = data?.violations?.summary || {};
    const types = ['all', 'red_light', 'stop_line', 'wrong_lane', 'lane_discipline'];
    const lanes = ['all', 'NORTH', 'SOUTH', 'EAST', 'WEST'];

    const filtered = violations.filter(v => {
        if (filterType !== 'all' && v.violation_type !== filterType) return false;
        if (filterLane !== 'all' && v.lane_id !== filterLane) return false;
        return true;
    });

    const severityColor = (type) => ({
        red_light: 'text-status-red',
        stop_line: 'text-status-amber',
        wrong_lane: 'text-status-amber',
        lane_discipline: 'text-text-secondary',
    }[type] || 'text-text-secondary');

    const severityBadge = (type) => ({
        red_light: 'status-badge--red',
        stop_line: 'status-badge--amber',
        wrong_lane: 'status-badge--amber',
        lane_discipline: 'status-badge--green',
    }[type] || 'status-badge--green');

    return (
        <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-text-heading uppercase tracking-wider">Violations Monitor</h2>
                <div className="text-2xs text-text-muted">
                    Total: <span className="font-mono text-status-red font-semibold">{summary.total_violations || 0}</span>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-4 gap-3">
                {Object.entries(summary.by_type || {}).map(([type, count]) => (
                    <div key={type} className="panel p-3">
                        <div className="text-2xs text-text-muted uppercase">{type.replace('_', ' ')}</div>
                        <div className={`font-mono text-xl font-bold mt-1 ${count > 0 ? severityColor(type) : 'text-text-muted'}`}>{count}</div>
                    </div>
                ))}
            </div>

            {/* Filters */}
            <div className="panel p-3 flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <span className="text-2xs text-text-muted uppercase font-semibold">Type:</span>
                    {types.map(t => (
                        <button key={t} onClick={() => setFilterType(t)} className={`text-2xs px-2 py-1 rounded transition-colors ${filterType === t ? 'bg-status-blue text-white' : 'text-text-secondary hover:bg-panel-bg'}`}>
                            {t === 'all' ? 'ALL' : t.replace('_', ' ').toUpperCase()}
                        </button>
                    ))}
                </div>
                <div className="h-4 w-px bg-panel-border" />
                <div className="flex items-center gap-2">
                    <span className="text-2xs text-text-muted uppercase font-semibold">Lane:</span>
                    {lanes.map(l => (
                        <button key={l} onClick={() => setFilterLane(l)} className={`text-2xs px-2 py-1 rounded transition-colors ${filterLane === l ? 'bg-status-blue text-white' : 'text-text-secondary hover:bg-panel-bg'}`}>
                            {l}
                        </button>
                    ))}
                </div>
            </div>

            {/* Violations Table */}
            <div className="panel">
                <div className="p-2">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Type</th>
                                <th>Lane</th>
                                <th>Vehicle</th>
                                <th>Confidence</th>
                                <th>Description</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.length > 0 ? filtered.slice(0, 50).map((v, i) => (
                                <tr key={i}>
                                    <td className="font-mono text-2xs">{v.timestamp?.split('T')[1] || v.timestamp}</td>
                                    <td><span className={`status-badge ${severityBadge(v.violation_type)}`}>{v.violation_type?.replace('_', ' ').toUpperCase()}</span></td>
                                    <td className="font-semibold">{v.lane_id}</td>
                                    <td className="text-text-secondary">{v.vehicle_class}</td>
                                    <td className="font-mono">{(v.confidence * 100).toFixed(0)}%</td>
                                    <td className="text-2xs text-text-muted max-w-xs truncate">{v.description}</td>
                                </tr>
                            )) : (
                                <tr><td colSpan={6} className="text-center text-text-muted py-8">No violations detected yet. Monitoring in progress...</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
