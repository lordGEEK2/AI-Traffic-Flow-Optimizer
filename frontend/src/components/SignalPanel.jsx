/**
 * SignalPanel — Traffic Signal Status and Control
 * Shows per-direction signal state, countdown timers, density,
 * and emergency control buttons. Government command center style.
 */
export default function SignalPanel({
    intersection,
    corridor,
    density,
    onTriggerEmergency,
    onClearEmergency,
}) {
    const signals = intersection?.signals || {};
    const directions = ['NORTH', 'SOUTH', 'EAST', 'WEST'];
    const emergencyActive = intersection?.emergency_active || false;
    const currentPhase = intersection?.current_phase || '';
    const phaseStage = intersection?.phase_stage || '';
    const cycleTime = intersection?.cycle_time || 0;
    const densityLanes = density?.lanes || [];

    const getDensityForDir = (dir) => {
        const lane = densityLanes.find(l => l.lane_id === dir);
        return lane?.smoothed_density?.toFixed(1) || '0.0';
    };

    const getSignalLightClass = (state) => {
        const map = {
            GREEN: 'signal-light--green',
            YELLOW: 'signal-light--yellow',
            RED: 'signal-light--red',
            EMERGENCY_OVERRIDE: 'signal-light--override',
        };
        return map[state] || 'signal-light--off';
    };

    const getStateLabel = (state) => {
        if (state === 'EMERGENCY_OVERRIDE') return 'OVERRIDE';
        return state || 'RED';
    };

    const getStateBadgeClass = (state) => {
        const map = {
            GREEN: 'status-badge--green',
            YELLOW: 'status-badge--amber',
            RED: 'status-badge--red',
            EMERGENCY_OVERRIDE: 'status-badge--blue',
        };
        return map[state] || 'status-badge--red';
    };

    return (
        <div className="panel flex-1">
            <div className="panel-header flex items-center justify-between">
                <span>Signal Control -- {intersection?.intersection_id || 'INT-001'}</span>
                <div className="flex items-center gap-2">
                    <span className="text-2xs font-mono text-text-muted">
                        CYCLE: {cycleTime.toFixed(0)}s
                    </span>
                    {emergencyActive && (
                        <span className="status-badge status-badge--red">PREEMPTED</span>
                    )}
                </div>
            </div>

            <div className="p-2">
                {/* Signal States */}
                <table className="data-table">
                    <thead>
                        <tr>
                            <th>Direction</th>
                            <th>Signal</th>
                            <th>State</th>
                            <th>Countdown</th>
                            <th>Density</th>
                        </tr>
                    </thead>
                    <tbody>
                        {directions.map(dir => {
                            const sig = signals[dir] || {};
                            return (
                                <tr key={dir} className={currentPhase === dir ? 'bg-panel-hover' : ''}>
                                    <td className="font-semibold text-text-heading">{dir}</td>
                                    <td>
                                        <div className="flex items-center gap-1">
                                            <span className={`signal-light ${sig.state === 'RED' || sig.state === 'EMERGENCY_OVERRIDE' ? 'signal-light--red' : 'signal-light--off'}`} style={{ width: 12, height: 12 }}></span>
                                            <span className={`signal-light ${sig.state === 'YELLOW' ? 'signal-light--yellow' : 'signal-light--off'}`} style={{ width: 12, height: 12 }}></span>
                                            <span className={`signal-light ${sig.state === 'GREEN' || sig.state === 'EMERGENCY_OVERRIDE' ? 'signal-light--green' : 'signal-light--off'}`} style={{ width: 12, height: 12 }}></span>
                                        </div>
                                    </td>
                                    <td>
                                        <span className={`status-badge ${getStateBadgeClass(sig.state)}`}>
                                            {getStateLabel(sig.state)}
                                        </span>
                                    </td>
                                    <td className="font-mono">
                                        {sig.countdown > 0 ? `${sig.countdown.toFixed(0)}s` : '--'}
                                    </td>
                                    <td className="font-mono text-text-secondary">
                                        {getDensityForDir(dir)}%
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>

                {/* Phase Info */}
                <div className="mt-2 pt-2 border-t border-panel-border flex items-center justify-between text-2xs font-mono text-text-muted">
                    <span>Phase: {currentPhase} / {phaseStage?.replace('_', ' ')}</span>
                    <span>Stage: {phaseStage || '--'}</span>
                </div>

                {/* Emergency Controls */}
                <div className="mt-3 pt-2 border-t border-panel-border">
                    <div className="text-2xs text-text-muted font-semibold uppercase tracking-wider mb-2">
                        Emergency Control
                    </div>
                    <div className="flex gap-2 flex-wrap">
                        {!emergencyActive ? (
                            directions.map(dir => (
                                <button
                                    key={dir}
                                    onClick={() => onTriggerEmergency(dir)}
                                    className="btn btn--danger text-2xs"
                                >
                                    TRIGGER {dir}
                                </button>
                            ))
                        ) : (
                            <button
                                onClick={onClearEmergency}
                                className="btn btn--success"
                            >
                                CLEAR EMERGENCY
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
