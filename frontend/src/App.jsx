import { useState, useEffect } from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import useWebSocket from './hooks/useWebSocket';
import CommandCenter from './pages/CommandCenter';
import CCTVAnalysis from './pages/CCTVAnalysis';
import ViolationsPage from './pages/ViolationsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SystemHealthPage from './pages/SystemHealthPage';

/**
 * App -- Delhi Smart Traffic Command & Analytics Platform
 * Root component with sidebar navigation and page routing.
 */
export default function App() {
    const { data, connected, sendCommand } = useWebSocket('ws://localhost:8000/ws');
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => setCurrentTime(new Date()), 1000);
        return () => clearInterval(timer);
    }, []);

    const formatTime = (d) => d.toLocaleTimeString('en-IN', { hour12: false });
    const formatDate = (d) => d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

    const navItems = [
        { path: '/', label: 'Command Center', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
        { path: '/cctv', label: 'CCTV Analysis', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M3 18h12a2 2 0 002-2V8a2 2 0 00-2-2H3a2 2 0 00-2 2v8a2 2 0 002 2z' },
        { path: '/violations', label: 'Violations', icon: 'M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
        { path: '/analytics', label: 'Analytics', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
        { path: '/system', label: 'System Health', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
    ];

    return (
        <div className="min-h-screen bg-panel-bg text-text-primary flex">
            {/* Sidebar */}
            <aside className="w-56 bg-panel-surface border-r border-panel-border flex flex-col shrink-0">
                <div className="px-4 py-3 border-b border-panel-border">
                    <div className="text-xs font-bold text-text-heading uppercase tracking-wider">Delhi Traffic AI</div>
                    <div className="text-2xs text-text-muted font-mono">ITO Intersection v3.0</div>
                </div>
                <nav className="flex-1 py-2">
                    {navItems.map(item => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            end={item.path === '/'}
                            className={({ isActive }) =>
                                `flex items-center gap-2 px-4 py-2 text-xs transition-colors ${isActive
                                    ? 'bg-status-blue/20 text-status-blue border-r-2 border-status-blue font-semibold'
                                    : 'text-text-secondary hover:bg-panel-bg hover:text-text-primary'
                                }`
                            }
                        >
                            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d={item.icon} />
                            </svg>
                            {item.label}
                        </NavLink>
                    ))}
                </nav>
                <div className="px-4 py-2 border-t border-panel-border text-2xs text-text-muted space-y-1">
                    <div className="flex justify-between">
                        <span>Status</span>
                        <span className={connected ? 'text-status-green' : 'text-status-red'}>{connected ? 'LIVE' : 'OFFLINE'}</span>
                    </div>
                    <div className="flex justify-between">
                        <span>Time</span>
                        <span className="font-mono">{formatTime(currentTime)}</span>
                    </div>
                    <div className="flex justify-between">
                        <span>Date</span>
                        <span className="font-mono">{formatDate(currentTime)}</span>
                    </div>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 overflow-auto">
                <Routes>
                    <Route path="/" element={<CommandCenter data={data} connected={connected} sendCommand={sendCommand} />} />
                    <Route path="/cctv" element={<CCTVAnalysis />} />
                    <Route path="/violations" element={<ViolationsPage data={data} />} />
                    <Route path="/analytics" element={<AnalyticsPage data={data} />} />
                    <Route path="/system" element={<SystemHealthPage data={data} />} />
                </Routes>
            </main>
        </div>
    );
}
