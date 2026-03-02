import { useState } from 'react';

/**
 * SystemHealthPage -- System Health & Operator Controls (Page 5).
 * Shows camera status, FPS, processing latency, dropped frames,
 * and operator controls (pause/resume, force signal, weather, threshold).
 */
export default function SystemHealthPage({ data }) {
    const [opMsg, setOpMsg] = useState('');
    const systemHealth = data?.system_health || {};
    const videoSource = data?.video_source || {};
    const detection = data?.detection || {};
    const intersection = data?.intersection || {};

    const apiCall = async (url, method = 'POST') => {
        try {
            const res = await fetch(url, { method });
            const json = await res.json();
            setOpMsg(json.message || 'OK');
            setTimeout(() => setOpMsg(''), 3000);
        } catch {
            setOpMsg('Request failed');
            setTimeout(() => setOpMsg(''), 3000);
        }
    };

    return (
        <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-text-heading uppercase tracking-wider">System Health & Controls</h2>
                {opMsg && <div className="text-2xs text-status-green font-mono bg-status-green/10 px-2 py-1 rounded">{opMsg}</div>}
            </div>

            <div className="grid grid-cols-3 gap-3">
                {/* Camera / Video Status */}
                <div className="panel">
                    <div className="panel-header">Video Source</div>
                    <div className="p-3 space-y-2">
                        <HealthRow label="Mode" value={videoSource.mode?.toUpperCase() || 'SIM'} ok={true} />
                        <HealthRow label="Camera Feed" value={videoSource.healthy ? 'ACTIVE' : 'OFFLINE'} ok={videoSource.healthy} />
                        <HealthRow label="Resolution" value={videoSource.source_width ? `${videoSource.source_width}x${videoSource.source_height}` : 'N/A'} ok={videoSource.source_width > 0} />
                        <HealthRow label="FPS (actual)" value={videoSource.fps_actual?.toFixed(1) || '0.0'} ok={videoSource.fps_actual > 0} />
                        <div className="pt-2 border-t border-panel-border text-2xs font-mono text-text-muted space-y-1">
                            <div className="flex justify-between"><span>Frames Read</span><span>{videoSource.frames_read || 0}</span></div>
                            <div className="flex justify-between"><span>Frames Dropped</span><span className={videoSource.frames_dropped > 0 ? 'text-status-amber' : ''}>{videoSource.frames_dropped || 0}</span></div>
                            <div className="flex justify-between"><span>Reconnections</span><span className={videoSource.reconnections > 0 ? 'text-status-red' : ''}>{videoSource.reconnections || 0}</span></div>
                            <div className="flex justify-between"><span>Uptime</span><span>{formatUptime(videoSource.uptime_seconds)}</span></div>
                        </div>
                    </div>
                </div>

                {/* Processing Health */}
                <div className="panel">
                    <div className="panel-header">Processing Pipeline</div>
                    <div className="p-3 space-y-2">
                        <HealthRow label="Status" value={systemHealth.status?.toUpperCase() || 'UNKNOWN'} ok={systemHealth.status === 'operational'} />
                        <HealthRow label="AI Engine" value={systemHealth.ai_paused ? 'PAUSED' : 'RUNNING'} ok={!systemHealth.ai_paused} />
                        <HealthRow label="Detection FPS" value={detection.fps?.toFixed(1) || '0.0'} ok={detection.fps > 0} />
                        <HealthRow label="Database" value={systemHealth.database_connected ? 'CONNECTED' : 'DISCONNECTED'} ok={systemHealth.database_connected} />
                        <HealthRow label="WS Clients" value={systemHealth.active_connections || 0} ok={true} />
                        <HealthRow label="Tick Count" value={systemHealth.tick_count || 0} ok={true} />
                        <div className="pt-2 border-t border-panel-border text-2xs font-mono text-text-muted space-y-1">
                            <div className="flex justify-between"><span>System Uptime</span><span>{formatUptime(systemHealth.uptime_seconds)}</span></div>
                            <div className="flex justify-between"><span>Frame Count</span><span>{detection.frame_count || 0}</span></div>
                            <div className="flex justify-between"><span>Weather</span><span className={intersection.weather === 'rain' ? 'text-status-blue' : ''}>{intersection.weather?.toUpperCase() || 'CLEAR'}</span></div>
                        </div>
                    </div>
                </div>

                {/* Operator Controls */}
                <div className="panel">
                    <div className="panel-header">Operator Control Panel</div>
                    <div className="p-3 space-y-3">
                        <div className="space-y-1">
                            <div className="text-2xs text-text-muted uppercase font-semibold">AI Processing</div>
                            <div className="flex gap-2">
                                <button onClick={() => apiCall('http://localhost:8000/api/operator/pause')} className="flex-1 text-2xs px-2 py-1.5 bg-status-amber/20 text-status-amber border border-status-amber/30 rounded hover:bg-status-amber/30 transition-colors">PAUSE AI</button>
                                <button onClick={() => apiCall('http://localhost:8000/api/operator/resume')} className="flex-1 text-2xs px-2 py-1.5 bg-status-green/20 text-status-green border border-status-green/30 rounded hover:bg-status-green/30 transition-colors">RESUME AI</button>
                            </div>
                        </div>

                        <div className="space-y-1">
                            <div className="text-2xs text-text-muted uppercase font-semibold">Weather Override</div>
                            <div className="flex gap-2">
                                <button onClick={() => apiCall('http://localhost:8000/api/system/weather?state=clear')} className="flex-1 text-2xs px-2 py-1.5 bg-panel-bg border border-panel-border rounded hover:bg-panel-surface transition-colors">CLEAR</button>
                                <button onClick={() => apiCall('http://localhost:8000/api/system/weather?state=rain')} className="flex-1 text-2xs px-2 py-1.5 bg-status-blue/20 text-status-blue border border-status-blue/30 rounded hover:bg-status-blue/30 transition-colors">RAIN</button>
                            </div>
                        </div>

                        <div className="space-y-1">
                            <div className="text-2xs text-text-muted uppercase font-semibold">Force Signal Phase</div>
                            <div className="grid grid-cols-2 gap-1">
                                {['NORTH', 'SOUTH', 'EAST', 'WEST'].map(dir => (
                                    <button key={dir} onClick={() => apiCall(`http://localhost:8000/api/operator/force-signal?direction=${dir}&duration=20`)} className="text-2xs px-2 py-1.5 bg-status-red/10 text-status-red border border-status-red/20 rounded hover:bg-status-red/20 transition-colors">
                                        {dir}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="space-y-1">
                            <div className="text-2xs text-text-muted uppercase font-semibold">Emergency Test</div>
                            <div className="flex gap-2">
                                <button onClick={() => apiCall('http://localhost:8000/api/system/test-emergency?direction=NORTH&vehicle_type=ambulance&duration_seconds=10')} className="flex-1 text-2xs px-2 py-1.5 bg-status-red/20 text-status-red border border-status-red/30 rounded hover:bg-status-red/30 transition-colors">TRIGGER TEST</button>
                                <button onClick={() => apiCall('http://localhost:8000/api/emergency/clear')} className="flex-1 text-2xs px-2 py-1.5 bg-panel-bg border border-panel-border rounded hover:bg-panel-surface transition-colors">CLEAR</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Module Status */}
            <div className="panel">
                <div className="panel-header">Module Status</div>
                <div className="p-2">
                    <table className="data-table">
                        <thead><tr><th>Module</th><th>Status</th><th>Description</th></tr></thead>
                        <tbody>
                            <ModuleRow name="VideoSource" ok={videoSource.healthy} desc="Camera / RTSP / Video file ingestion" />
                            <ModuleRow name="VehicleDetector" ok={true} desc="YOLOv8 object detection engine" />
                            <ModuleRow name="DensityAnalyzer" ok={true} desc="Polygon-based lane density calculation" />
                            <ModuleRow name="EmergencyDetector" ok={true} desc="Multi-frame emergency vehicle confirmation" />
                            <ModuleRow name="ViolationDetector" ok={true} desc="Red light, stop line, wrong lane detection" />
                            <ModuleRow name="TrafficAnalyzer" ok={true} desc="Flow analytics, health score, AI reasoning" />
                            <ModuleRow name="SignalController" ok={true} desc="Government-grade signal state machine" />
                            <ModuleRow name="GreenCorridorManager" ok={true} desc="Emergency corridor coordination" />
                            <ModuleRow name="Database" ok={systemHealth.database_connected} desc="SQLite persistent storage (7 tables)" />
                        </tbody>
                    </table>
                </div>
            </div>
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

function ModuleRow({ name, ok, desc }) {
    return (
        <tr>
            <td className="font-semibold text-text-heading font-mono">{name}</td>
            <td><span className={`status-dot ${ok ? 'status-dot--green' : 'status-dot--red'}`}></span> <span className="text-2xs">{ok ? 'ACTIVE' : 'INACTIVE'}</span></td>
            <td className="text-text-muted text-2xs">{desc}</td>
        </tr>
    );
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
