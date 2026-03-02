/**
 * EmergencyAlert — Professional emergency corridor notification bar.
 * Displays when a green corridor is active.
 * Red left-border bar with structured information, no flashy animations.
 */
export default function EmergencyAlert({ corridor, alerts, onClear }) {
    const latestAlert = alerts?.[alerts.length - 1] || {};

    return (
        <div className="emergency-bar mx-3 mt-2 p-3 flex items-center justify-between">
            <div className="flex items-center gap-4">
                {/* Status indicator */}
                <div className="flex items-center gap-2">
                    <span className="status-dot status-dot--red" style={{ width: 10, height: 10 }}></span>
                    <span className="text-sm font-semibold text-status-red uppercase tracking-wide">
                        Emergency Active
                    </span>
                </div>

                {/* Details */}
                <div className="flex items-center gap-3 text-xs font-mono text-text-secondary">
                    <span className="text-panel-border">|</span>
                    <span>
                        TYPE: <span className="text-text-heading">{corridor?.vehicle_type?.toUpperCase() || 'UNKNOWN'}</span>
                    </span>
                    <span>
                        DIR: <span className="text-text-heading">{corridor?.direction || '--'}</span>
                    </span>
                    <span>
                        DURATION: <span className="text-text-heading">{corridor?.duration?.toFixed(0) || 0}s</span>
                    </span>
                    {corridor?.corridor_path?.length > 0 && (
                        <span>
                            PATH: <span className="text-status-blue">{corridor.corridor_path.join(' > ')}</span>
                        </span>
                    )}
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
                {latestAlert?.message && (
                    <span className="text-2xs text-text-muted max-w-xs truncate">{latestAlert.message}</span>
                )}
                <button onClick={onClear} className="btn btn--success">
                    CLEAR
                </button>
            </div>
        </div>
    );
}
