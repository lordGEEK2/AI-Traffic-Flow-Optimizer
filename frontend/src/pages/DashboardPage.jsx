import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * DashboardPage — Live Traffic Dashboard
 * 2x2 grid of annotated video feeds with traffic lights, density, and ambulance status.
 */
export default function DashboardPage() {
    const navigate = useNavigate();
    const [laneData, setLaneData] = useState({});
    const [connected, setConnected] = useState(false);
    const [processing, setProcessing] = useState(false);
    const wsRef = useRef(null);
    const frameTimerRef = useRef(null);
    const [frameVersion, setFrameVersion] = useState(0);

    // WebSocket for real-time lane data
    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8000/ws');
        ws.onopen = () => setConnected(true);
        ws.onclose = () => setConnected(false);
        ws.onerror = () => setConnected(false);
        ws.onmessage = (e) => {
            try {
                const data = JSON.parse(e.data);
                setLaneData(data);
                setProcessing(data.processing || false);
            } catch (err) { /* ignore */ }
        };
        wsRef.current = ws;
        return () => { ws.close(); };
    }, []);

    // Refresh frame images periodically
    useEffect(() => {
        frameTimerRef.current = setInterval(() => {
            setFrameVersion(v => v + 1);
        }, 600);
        return () => clearInterval(frameTimerRef.current);
    }, []);

    const lanes = ['Lane 1', 'Lane 2', 'Lane 3', 'Lane 4'];

    const getLaneInfo = (laneId) => {
        const ld = laneData?.lanes?.[laneId];
        return {
            density: ld?.density ?? 0,
            ambulance: ld?.ambulance ?? false,
            signal: ld?.signal ?? 'red',
            greenTime: ld?.green_time ?? null,
        };
    };

    const TrafficLight = ({ color }) => {
        const isRed = color !== 'green';
        const isGreen = color === 'green';
        return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', background: '#1a1a2e', borderRadius: '8px', padding: '6px', border: '2px solid #333' }}>
                <div style={{
                    width: '22px', height: '22px', borderRadius: '50%',
                    background: isRed ? '#ef4444' : '#333', boxShadow: isRed ? '0 0 12px #ef4444' : 'none',
                }} />
                <div style={{
                    width: '22px', height: '22px', borderRadius: '50%',
                    background: '#daa520', opacity: 0.3,
                }} />
                <div style={{
                    width: '22px', height: '22px', borderRadius: '50%',
                    background: isGreen ? '#22c55e' : '#333', boxShadow: isGreen ? '0 0 12px #22c55e' : 'none',
                }} />
            </div>
        );
    };

    return (
        <div style={{
            minHeight: '100vh', background: '#f5f5f5',
            fontFamily: "'Inter', 'Segoe UI', sans-serif",
        }}>
            {/* Header */}
            <header style={{
                padding: '16px 32px', background: '#fff',
                borderBottom: '1px solid #e0e0e0',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
                <h1 style={{ fontSize: '22px', fontWeight: 700, color: '#1a1a2e' }}>
                    Live Traffic Dashboard
                </h1>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '6px',
                        fontSize: '12px', fontWeight: 600,
                        color: connected ? '#22c55e' : '#ef4444',
                    }}>
                        <span style={{
                            width: '8px', height: '8px', borderRadius: '50%',
                            background: connected ? '#22c55e' : '#ef4444',
                        }} />
                        {connected ? 'CONNECTED' : 'DISCONNECTED'}
                    </span>
                    {processing && (
                        <span style={{
                            background: '#22c55e', color: '#fff', padding: '4px 12px',
                            borderRadius: '12px', fontSize: '11px', fontWeight: 700,
                        }}>
                            PROCESSING
                        </span>
                    )}
                </div>
            </header>

            {/* 2x2 Grid */}
            <div style={{
                display: 'grid', gridTemplateColumns: '1fr 1fr',
                gap: '12px', padding: '16px 24px', maxWidth: '1200px', margin: '0 auto',
            }}>
                {lanes.map((lane, idx) => {
                    const info = getLaneInfo(lane);
                    return (
                        <div key={lane} style={{
                            background: '#1a1a2e', borderRadius: '12px', overflow: 'hidden',
                            border: info.ambulance ? '3px solid #ef4444' : '1px solid #333',
                            position: 'relative',
                        }}>
                            {/* Video Feed */}
                            <div style={{ position: 'relative', display: 'flex' }}>
                                <div style={{ position: 'absolute', top: '8px', left: '8px', zIndex: 2 }}>
                                    <TrafficLight color={info.signal} />
                                </div>
                                <img
                                    src={`http://localhost:8000/api/frames/${idx + 1}?v=${frameVersion}`}
                                    alt={lane}
                                    style={{
                                        width: '100%', height: '300px', objectFit: 'cover',
                                        background: '#0a0a1e',
                                    }}
                                    onError={(e) => { e.target.style.opacity = '0.5'; }}
                                />
                            </div>
                            {/* Status Bar */}
                            <div style={{
                                padding: '8px 14px', background: 'rgba(0,0,0,0.9)',
                                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                                fontSize: '13px', color: '#ccc', fontFamily: 'monospace',
                            }}>
                                <span>Density: <b style={{ color: '#fff' }}>{info.density}</b></span>
                                <span>
                                    Ambulance:{' '}
                                    <b style={{ color: info.ambulance ? '#ef4444' : '#888' }}>
                                        {info.ambulance ? 'YES!' : 'No'}
                                    </b>
                                </span>
                                <span>
                                    Time:{' '}
                                    <b style={{ color: '#4facfe' }}>
                                        {info.greenTime ? `${info.greenTime}s` : '--'}
                                    </b>
                                </span>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Action Buttons */}
            <div style={{
                display: 'flex', justifyContent: 'center', gap: '16px',
                padding: '24px 0 40px',
            }}>
                <button
                    onClick={() => navigate('/analysis')}
                    style={{
                        padding: '12px 28px', borderRadius: '8px', border: 'none',
                        background: '#22c55e', color: '#fff', fontWeight: 700,
                        fontSize: '14px', cursor: 'pointer',
                    }}
                >
                    View Analysis
                </button>
                <button
                    onClick={() => navigate('/upload')}
                    style={{
                        padding: '12px 28px', borderRadius: '8px', border: 'none',
                        background: '#3b82f6', color: '#fff', fontWeight: 700,
                        fontSize: '14px', cursor: 'pointer',
                    }}
                >
                    Upload New Videos
                </button>
                <button
                    onClick={() => navigate('/')}
                    style={{
                        padding: '12px 28px', borderRadius: '8px', border: 'none',
                        background: '#6b7280', color: '#fff', fontWeight: 700,
                        fontSize: '14px', cursor: 'pointer',
                    }}
                >
                    Back to Home
                </button>
            </div>
        </div>
    );
}
