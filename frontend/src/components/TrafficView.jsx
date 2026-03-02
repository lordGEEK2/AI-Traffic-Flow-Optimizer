/**
 * TrafficView — Intersection Schematic Visualization
 * SVG-based top-down intersection map showing:
 *  - 4-way roads with lane markings
 *  - Density-colored lane fills
 *  - Traffic light indicators per direction
 *  - Phase directional arrows
 *  - Emergency corridor route overlay
 *  - Vehicle counts per lane
 * Government command center style, zoom-safe.
 */
export default function TrafficView({ intersection, density, corridor }) {
    const signals = intersection?.signals || {};
    const lanes = density?.lanes || [];
    const corridorActive = corridor?.active || false;
    const corridorDir = corridor?.direction || '';

    const getDensity = (dir) => {
        const l = lanes.find(l => l.lane_id === dir);
        return l?.smoothed_density || l?.raw_density || 0;
    };

    const getLevel = (dir) => {
        const l = lanes.find(l => l.lane_id === dir);
        return l?.level || 'low';
    };

    const getCount = (dir) => {
        const l = lanes.find(l => l.lane_id === dir);
        return l?.vehicle_count || 0;
    };

    const getSignalState = (dir) => signals[dir]?.state || 'RED';

    const levelFill = (level) => {
        const map = {
            low: 'rgba(34,197,94,0.12)',
            medium: 'rgba(245,158,11,0.15)',
            high: 'rgba(239,68,68,0.15)',
            critical: 'rgba(239,68,68,0.25)',
        };
        return map[level] || 'rgba(34,197,94,0.1)';
    };

    const signalColor = (state) => {
        const map = { GREEN: '#22c55e', YELLOW: '#f59e0b', RED: '#ef4444', EMERGENCY_OVERRIDE: '#3b82f6' };
        return map[state] || '#ef4444';
    };

    return (
        <div className="panel flex-1">
            <div className="panel-header flex items-center justify-between">
                <span>Intersection Schematic -- {intersection?.intersection_id || 'INT-001'}</span>
                {corridorActive && (
                    <span className="status-badge status-badge--blue">
                        CORRIDOR: {corridorDir}
                    </span>
                )}
            </div>
            <div className="p-2 flex items-center justify-center">
                <svg viewBox="0 0 300 300" className="w-full max-w-xs" style={{ maxHeight: 280 }}>
                    {/* Background */}
                    <rect x="0" y="0" width="300" height="300" fill="#0a0e17" />

                    {/* Road areas */}
                    {/* Horizontal road */}
                    <rect x="0" y="120" width="300" height="60" fill="#1a2332" stroke="#2a3548" strokeWidth="0.5" />
                    {/* Vertical road */}
                    <rect x="120" y="0" width="60" height="300" fill="#1a2332" stroke="#2a3548" strokeWidth="0.5" />
                    {/* Center intersection box */}
                    <rect x="120" y="120" width="60" height="60" fill="#1f2937" stroke="#2a3548" strokeWidth="0.5" />

                    {/* Lane density fills */}
                    {/* North */}
                    <rect x="120" y="0" width="60" height="120" fill={levelFill(getLevel('NORTH'))} />
                    {/* South */}
                    <rect x="120" y="180" width="60" height="120" fill={levelFill(getLevel('SOUTH'))} />
                    {/* East */}
                    <rect x="180" y="120" width="120" height="60" fill={levelFill(getLevel('EAST'))} />
                    {/* West */}
                    <rect x="0" y="120" width="120" height="60" fill={levelFill(getLevel('WEST'))} />

                    {/* Center lane markings (dashed) */}
                    <line x1="150" y1="0" x2="150" y2="120" stroke="#2a3548" strokeWidth="1" strokeDasharray="6,4" />
                    <line x1="150" y1="180" x2="150" y2="300" stroke="#2a3548" strokeWidth="1" strokeDasharray="6,4" />
                    <line x1="0" y1="150" x2="120" y2="150" stroke="#2a3548" strokeWidth="1" strokeDasharray="6,4" />
                    <line x1="180" y1="150" x2="300" y2="150" stroke="#2a3548" strokeWidth="1" strokeDasharray="6,4" />

                    {/* Emergency corridor overlay */}
                    {corridorActive && corridorDir === 'NORTH' && <rect x="120" y="0" width="60" height="120" fill="rgba(59,130,246,0.2)" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="4,3" />}
                    {corridorActive && corridorDir === 'SOUTH' && <rect x="120" y="180" width="60" height="120" fill="rgba(59,130,246,0.2)" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="4,3" />}
                    {corridorActive && corridorDir === 'EAST' && <rect x="180" y="120" width="120" height="60" fill="rgba(59,130,246,0.2)" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="4,3" />}
                    {corridorActive && corridorDir === 'WEST' && <rect x="0" y="120" width="120" height="60" fill="rgba(59,130,246,0.2)" stroke="#3b82f6" strokeWidth="1.5" strokeDasharray="4,3" />}

                    {/* Traffic lights (positioned at stop lines) */}
                    {/* North */}
                    <circle cx="150" cy="115" r="5" fill={signalColor(getSignalState('NORTH'))} />
                    {/* South */}
                    <circle cx="150" cy="185" r="5" fill={signalColor(getSignalState('SOUTH'))} />
                    {/* East */}
                    <circle cx="185" cy="150" r="5" fill={signalColor(getSignalState('EAST'))} />
                    {/* West */}
                    <circle cx="115" cy="150" r="5" fill={signalColor(getSignalState('WEST'))} />

                    {/* Phase arrows for GREEN signals */}
                    {getSignalState('NORTH') === 'GREEN' && <polygon points="150,105 145,95 155,95" fill="#22c55e" opacity="0.8" />}
                    {getSignalState('SOUTH') === 'GREEN' && <polygon points="150,195 145,205 155,205" fill="#22c55e" opacity="0.8" />}
                    {getSignalState('EAST') === 'GREEN' && <polygon points="195,150 205,145 205,155" fill="#22c55e" opacity="0.8" />}
                    {getSignalState('WEST') === 'GREEN' && <polygon points="105,150 95,145 95,155" fill="#22c55e" opacity="0.8" />}

                    {/* Vehicle counts (outside intersection) */}
                    <text x="150" y="55" textAnchor="middle" fill="#e5e7eb" fontSize="11" fontFamily="JetBrains Mono, monospace" fontWeight="600">{getCount('NORTH')}</text>
                    <text x="150" y="65" textAnchor="middle" fill="#9ca3af" fontSize="7" fontFamily="Inter, sans-serif">NORTH</text>

                    <text x="150" y="250" textAnchor="middle" fill="#e5e7eb" fontSize="11" fontFamily="JetBrains Mono, monospace" fontWeight="600">{getCount('SOUTH')}</text>
                    <text x="150" y="260" textAnchor="middle" fill="#9ca3af" fontSize="7" fontFamily="Inter, sans-serif">SOUTH</text>

                    <text x="245" y="148" textAnchor="middle" fill="#e5e7eb" fontSize="11" fontFamily="JetBrains Mono, monospace" fontWeight="600">{getCount('EAST')}</text>
                    <text x="245" y="158" textAnchor="middle" fill="#9ca3af" fontSize="7" fontFamily="Inter, sans-serif">EAST</text>

                    <text x="55" y="148" textAnchor="middle" fill="#e5e7eb" fontSize="11" fontFamily="JetBrains Mono, monospace" fontWeight="600">{getCount('WEST')}</text>
                    <text x="55" y="158" textAnchor="middle" fill="#9ca3af" fontSize="7" fontFamily="Inter, sans-serif">WEST</text>

                    {/* Density percentages */}
                    <text x="150" y="78" textAnchor="middle" fill="#6b7280" fontSize="7" fontFamily="JetBrains Mono, monospace">{getDensity('NORTH').toFixed(0)}%</text>
                    <text x="150" y="237" textAnchor="middle" fill="#6b7280" fontSize="7" fontFamily="JetBrains Mono, monospace">{getDensity('SOUTH').toFixed(0)}%</text>
                    <text x="245" y="170" textAnchor="middle" fill="#6b7280" fontSize="7" fontFamily="JetBrains Mono, monospace">{getDensity('EAST').toFixed(0)}%</text>
                    <text x="55" y="170" textAnchor="middle" fill="#6b7280" fontSize="7" fontFamily="JetBrains Mono, monospace">{getDensity('WEST').toFixed(0)}%</text>

                    {/* Intersection ID */}
                    <text x="150" y="154" textAnchor="middle" fill="#4b5563" fontSize="7" fontFamily="JetBrains Mono, monospace">{intersection?.intersection_id || 'INT-001'}</text>
                </svg>
            </div>
        </div>
    );
}
