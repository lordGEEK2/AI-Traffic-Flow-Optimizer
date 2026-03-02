import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

/**
 * AnalyticsPage — Analysis Dashboard
 * Clean white background. Vehicle count table, density bar chart, efficiency comparison.
 */
export default function AnalyticsPage() {
    const navigate = useNavigate();
    const [stats, setStats] = useState(null);
    const [efficiency, setEfficiency] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, effRes] = await Promise.all([
                    fetch('http://localhost:8000/api/lane-stats'),
                    fetch('http://localhost:8000/api/efficiency'),
                ]);
                if (statsRes.ok) setStats(await statsRes.json());
                if (effRes.ok) setEfficiency(await effRes.json());
            } catch (err) {
                console.error('Failed to fetch analytics', err);
            }
        };
        fetchData();
        const timer = setInterval(fetchData, 3000);
        return () => clearInterval(timer);
    }, []);

    const lanes = ['Lane 1', 'Lane 2', 'Lane 3', 'Lane 4'];

    // Vehicle count table data
    const tableData = lanes.map(lid => {
        const s = stats?.lanes?.[lid] ?? {};
        return {
            lane: lid,
            cars: s.cars ?? 0,
            buses: s.buses ?? 0,
            trucks: s.trucks ?? 0,
            motorcycles: s.motorcycles ?? 0,
            ambulances: s.ambulances ?? 0,
            total: s.total ?? 0,
        };
    });

    // Density chart data (use total from stats)
    const densityData = lanes.map(lid => ({
        name: lid,
        density: stats?.lanes?.[lid]?.total ?? 0,
    }));

    // Efficiency chart data
    const efficiencyData = lanes.map(lid => {
        const e = efficiency?.lanes?.[lid];
        return {
            name: lid,
            smart: e?.smart_avg ?? 20,
            traditional: e?.traditional_avg ?? 30,
        };
    });

    const sectionStyle = {
        background: '#fff', borderRadius: '12px', padding: '28px',
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)', marginBottom: '24px',
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
                    Analysis Dashboard
                </h1>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                        onClick={() => navigate('/dashboard')}
                        style={{
                            padding: '8px 20px', borderRadius: '6px', border: 'none',
                            background: '#3b82f6', color: '#fff', fontWeight: 600,
                            fontSize: '13px', cursor: 'pointer',
                        }}
                    >
                        Back to Dashboard
                    </button>
                </div>
            </header>

            <div style={{ padding: '24px 32px', maxWidth: '1000px', margin: '0 auto' }}>
                {/* Cumulative Vehicles Passed Table */}
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#1a1a2e', marginBottom: '4px', textAlign: 'center' }}>
                        Cumulative Vehicles Passed (Per Lane)
                    </h2>
                    <p style={{ color: '#888', fontSize: '13px', textAlign: 'center', marginBottom: '20px' }}>
                        Total vehicles counted when their lane's light turned red.
                    </p>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ borderBottom: '2px solid #e0e0e0' }}>
                                {['Lane', 'Cars', 'Buses', 'Trucks', 'Motorcycles', 'Ambulances', 'Total'].map(h => (
                                    <th key={h} style={{
                                        padding: '10px 16px', textAlign: 'left',
                                        fontSize: '13px', fontWeight: 700, color: '#444',
                                    }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {tableData.map((row, i) => (
                                <tr key={row.lane} style={{
                                    borderBottom: '1px solid #eee',
                                    background: i % 2 === 0 ? '#fff' : '#fafafa',
                                }}>
                                    <td style={{ padding: '10px 16px', fontWeight: 600, fontSize: '13px', fontFamily: 'monospace' }}>{row.lane}</td>
                                    <td style={{ padding: '10px 16px', fontSize: '14px' }}>{row.cars}</td>
                                    <td style={{ padding: '10px 16px', fontSize: '14px' }}>{row.buses}</td>
                                    <td style={{ padding: '10px 16px', fontSize: '14px' }}>{row.trucks}</td>
                                    <td style={{ padding: '10px 16px', fontSize: '14px' }}>{row.motorcycles}</td>
                                    <td style={{ padding: '10px 16px', fontSize: '14px', color: row.ambulances > 0 ? '#ef4444' : '#888', fontWeight: row.ambulances > 0 ? 700 : 400 }}>
                                        {row.ambulances}
                                    </td>
                                    <td style={{ padding: '10px 16px', fontSize: '14px', fontWeight: 700 }}>{row.total}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Current Traffic Density */}
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#1a1a2e', marginBottom: '4px', textAlign: 'center' }}>
                        Current Traffic Density (Live)
                    </h2>
                    <p style={{ color: '#888', fontSize: '13px', textAlign: 'center', marginBottom: '20px' }}>
                        Live snapshot of vehicle count in each lane.
                    </p>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={densityData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                            <XAxis dataKey="name" fontSize={13} />
                            <YAxis fontSize={13} />
                            <Tooltip />
                            <Legend />
                            <Bar dataKey="density" fill="#f87171" name="Current Vehicle Density" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* System Efficiency */}
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: '18px', fontWeight: 700, color: '#1a1a2e', marginBottom: '4px', textAlign: 'center' }}>
                        System Efficiency (Smart vs. Traditional)
                    </h2>
                    <p style={{ color: '#888', fontSize: '13px', textAlign: 'center', marginBottom: '20px' }}>
                        Compares the dynamic green light time (Smart) vs. a fixed 30 second timer (Traditional).
                    </p>
                    <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={efficiencyData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                            <XAxis dataKey="name" fontSize={13} />
                            <YAxis label={{ value: 'Green Light Time (seconds)', angle: -90, position: 'insideLeft', fontSize: 12 }} fontSize={13} />
                            <Tooltip />
                            <Legend />
                            <Bar dataKey="smart" fill="#67e8f9" name="Smart System (Dynamic Time)" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="traditional" fill="#fca5a5" name="Traditional System (Fixed Time)" radius={[4, 4, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>
        </div>
    );
}
