import { useState, useEffect } from 'react';
import useWebSocket from './hooks/useWebSocket';
import Dashboard from './components/Dashboard';
import SignalPanel from './components/SignalPanel';
import TrafficView from './components/TrafficView';
import EmergencyAlert from './components/EmergencyAlert';

/**
 * App — Root component for the Smart Traffic Command Center.
 * Professional government-grade control interface.
 */
export default function App() {
    const { data, connected, sendCommand } = useWebSocket('ws://localhost:8000/ws');
    const [currentTime, setCurrentTime] = useState(new Date());

    // Update clock every second
    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const detection = data?.detection || {};
    const density = data?.density || {};
    const intersection = data?.intersection || {};
    const corridor = data?.corridor || {};
    const videoSource = data?.video_source || {};
    const systemHealth = data?.system_health || {};
    const alerts = data?.alerts || [];

    const formatTime = (d) => d.toLocaleTimeString('en-IN', { hour12: false });
    const formatDate = (d) => d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

    return (
        <div className="min-h-screen bg-panel-bg text-text-primary">
            {/* Header */}
            <header className="border-b border-panel-border bg-panel-surface px-4 py-2 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-status-blue"></div>
                    <h1 className="text-sm font-semibold tracking-wide text-text-heading uppercase">
                        Smart Traffic Command Center
                    </h1>
                    <span className="text-2xs text-text-muted font-mono">v2.0</span>
                </div>

                <div className="flex items-center gap-4">
                    {/* System Health Indicators */}
                    <div className="flex items-center gap-3 text-2xs font-mono text-text-secondary">
                        <span className="flex items-center gap-1">
                            VIDEO:
                            <span className={`status-dot ${videoSource.healthy ? 'status-dot--green' : 'status-dot--red'}`}></span>
                            <span className="text-text-muted">{videoSource.mode || 'SIM'}</span>
                        </span>
                        <span className="text-panel-border">|</span>
                        <span className="flex items-center gap-1">
                            DB:
                            <span className={`status-dot ${systemHealth.database_connected ? 'status-dot--green' : 'status-dot--amber'}`}></span>
                        </span>
                        <span className="text-panel-border">|</span>
                        <span>FPS: {detection.fps?.toFixed(1) || '0.0'}</span>
                        <span className="text-panel-border">|</span>
                        <span>CONN: {systemHealth.active_connections || 0}</span>
                    </div>

                    {/* Connection Status */}
                    <div className={`status-badge ${connected ? 'status-badge--green' : 'status-badge--red'}`}>
                        <span className={`status-dot ${connected ? 'status-dot--green' : 'status-dot--red'}`}></span>
                        {connected ? 'CONNECTED' : 'DISCONNECTED'}
                    </div>

                    {/* Clock */}
                    <div className="text-right font-mono text-2xs text-text-secondary leading-tight">
                        <div className="text-text-primary font-medium">{formatTime(currentTime)}</div>
                        <div>{formatDate(currentTime)}</div>
                    </div>
                </div>
            </header>

            {/* Emergency Alert Bar */}
            {corridor.active && (
                <EmergencyAlert
                    corridor={corridor}
                    alerts={alerts}
                    onClear={() => sendCommand({ action: 'clear_emergency' })}
                />
            )}

            {/* Main Grid */}
            <div className="p-3 grid grid-cols-12 gap-3" style={{ height: 'calc(100vh - 48px)' }}>
                {/* Left Column: Dashboard (8 cols) */}
                <div className="col-span-8 flex flex-col gap-3 overflow-auto">
                    <Dashboard
                        detection={detection}
                        density={density}
                        systemHealth={systemHealth}
                        videoSource={videoSource}
                    />
                </div>

                {/* Right Column: Signals + Map (4 cols) */}
                <div className="col-span-4 flex flex-col gap-3 overflow-auto">
                    <SignalPanel
                        intersection={intersection}
                        corridor={corridor}
                        density={density}
                        onTriggerEmergency={(dir) => sendCommand({
                            action: 'trigger_emergency',
                            direction: dir,
                            vehicle_type: 'ambulance',
                        })}
                        onClearEmergency={() => sendCommand({ action: 'clear_emergency' })}
                    />
                    <TrafficView
                        intersection={intersection}
                        density={density}
                        corridor={corridor}
                    />
                </div>
            </div>
        </div>
    );
}
