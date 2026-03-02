import { useNavigate } from 'react-router-dom';

/**
 * HomePage — ITMS Landing Page
 * Warm gradient background with feature cards and technology list.
 */
export default function HomePage() {
    const navigate = useNavigate();

    const features = [
        {
            title: 'Dynamic Signal Control',
            desc: 'Automatically adjusts green light duration based on real-time vehicle density, reducing unnecessary waiting times.',
            icon: '🚦',
        },
        {
            title: 'Ambulance Priority',
            desc: 'Detects emergency vehicles and provides an immediate green light corridor to reduce response times and save lives.',
            icon: '🚑',
        },
        {
            title: 'Live Dashboard',
            desc: 'Monitor up to four lanes simultaneously with real-time video feeds, vehicle detection boxes, and traffic light status.',
            icon: '📺',
        },
        {
            title: 'Data Analytics',
            desc: 'View detailed graphs on vehicle flow, lane density, and system efficiency compared to traditional methods.',
            icon: '📊',
        },
    ];

    const techStack = [
        { name: 'YOLOv8', desc: 'Object Detection' },
        { name: 'OpenCV', desc: 'Video Processing' },
        { name: 'FastAPI', desc: 'Backend API' },
        { name: 'React', desc: 'Frontend UI' },
        { name: 'WebSocket', desc: 'Real-time Comms' },
        { name: 'SQLite', desc: 'Data Storage' },
    ];

    return (
        <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 25%, #ff9a56 50%, #fecf6a 75%, #4facfe 100%)' }}>
            {/* Header */}
            <header style={{ padding: '30px 40px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h1 style={{ color: '#fff', fontSize: '24px', fontWeight: 700, textShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>
                    ITMS — Intelligent Traffic Management System
                </h1>
                <div style={{ display: 'flex', gap: '12px' }}>
                    <button
                        onClick={() => navigate('/upload')}
                        style={{
                            padding: '10px 24px', borderRadius: '8px', border: 'none',
                            background: 'rgba(255,255,255,0.9)', color: '#333', fontWeight: 600,
                            cursor: 'pointer', fontSize: '14px',
                        }}
                    >
                        Upload Videos
                    </button>
                    <button
                        onClick={() => navigate('/dashboard')}
                        style={{
                            padding: '10px 24px', borderRadius: '8px', border: '2px solid rgba(255,255,255,0.8)',
                            background: 'transparent', color: '#fff', fontWeight: 600,
                            cursor: 'pointer', fontSize: '14px',
                        }}
                    >
                        Dashboard
                    </button>
                </div>
            </header>

            {/* Hero Section */}
            <section style={{ textAlign: 'center', padding: '60px 40px 40px' }}>
                <h2 style={{ fontSize: '42px', fontWeight: 800, color: '#fff', marginBottom: '16px', textShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
                    Smart Traffic Control
                </h2>
                <p style={{ fontSize: '18px', color: 'rgba(255,255,255,0.9)', maxWidth: '600px', margin: '0 auto', lineHeight: 1.6 }}>
                    AI-powered traffic management system with real-time vehicle detection, ambulance priority corridors, and intelligent signal optimization.
                </p>
            </section>

            {/* Features */}
            <section style={{ padding: '40px' }}>
                <h3 style={{ textAlign: 'center', fontSize: '28px', fontWeight: 700, color: '#fff', marginBottom: '32px' }}>
                    Project Features
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', maxWidth: '1000px', margin: '0 auto' }}>
                    {features.map((f, i) => (
                        <div key={i} style={{
                            background: 'rgba(255,255,255,0.2)', backdropFilter: 'blur(12px)',
                            borderRadius: '16px', padding: '28px', textAlign: 'center',
                            border: '1px solid rgba(255,255,255,0.3)',
                            transition: 'transform 0.2s',
                        }}
                            onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-4px)'}
                            onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
                        >
                            <div style={{ fontSize: '40px', marginBottom: '12px' }}>{f.icon}</div>
                            <h4 style={{ fontSize: '17px', fontWeight: 700, color: '#fff', marginBottom: '8px' }}>{f.title}</h4>
                            <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.85)', lineHeight: 1.5 }}>{f.desc}</p>
                        </div>
                    ))}
                </div>
            </section>

            {/* Tools & Technology */}
            <section style={{ padding: '40px', textAlign: 'center' }}>
                <h3 style={{ fontSize: '28px', fontWeight: 700, color: '#fff', marginBottom: '24px' }}>
                    Tools & Technology
                </h3>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '16px' }}>
                    {techStack.map((t, i) => (
                        <div key={i} style={{
                            background: 'rgba(255,255,255,0.15)', backdropFilter: 'blur(8px)',
                            borderRadius: '10px', padding: '12px 24px',
                            border: '1px solid rgba(255,255,255,0.25)',
                        }}>
                            <div style={{ color: '#fff', fontWeight: 700, fontSize: '15px' }}>{t.name}</div>
                            <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '12px' }}>{t.desc}</div>
                        </div>
                    ))}
                </div>
            </section>

            {/* CTA */}
            <section style={{ textAlign: 'center', padding: '40px 40px 80px' }}>
                <button
                    onClick={() => navigate('/upload')}
                    style={{
                        padding: '16px 48px', borderRadius: '12px', border: 'none',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: '#fff', fontSize: '18px', fontWeight: 700,
                        cursor: 'pointer', boxShadow: '0 8px 24px rgba(102,126,234,0.4)',
                        transition: 'transform 0.2s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.05)'}
                    onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                >
                    Get Started — Upload Videos
                </button>
            </section>
        </div>
    );
}
