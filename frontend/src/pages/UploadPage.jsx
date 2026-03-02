import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * UploadPage — Upload 4 Lane Videos
 * Matches the ITMS reference: dark blue background, 4 file inputs, gradient "Upload and Start" button.
 */
export default function UploadPage() {
    const navigate = useNavigate();
    const [files, setFiles] = useState({ lane1: null, lane2: null, lane3: null, lane4: null });
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [error, setError] = useState('');

    const handleFileChange = (lane, e) => {
        const file = e.target.files[0];
        setFiles(prev => ({ ...prev, [lane]: file }));
        setError('');
    };

    const handleUpload = async () => {
        const { lane1, lane2, lane3, lane4 } = files;
        if (!lane1 || !lane2 || !lane3 || !lane4) {
            setError('Please select a video file for each lane.');
            return;
        }

        setUploading(true);
        setProgress(10);
        setError('');

        try {
            const formData = new FormData();
            formData.append('lane1', lane1);
            formData.append('lane2', lane2);
            formData.append('lane3', lane3);
            formData.append('lane4', lane4);

            setProgress(30);

            const uploadRes = await fetch('http://localhost:8000/api/upload', {
                method: 'POST',
                body: formData,
            });

            if (!uploadRes.ok) throw new Error('Upload failed');
            setProgress(60);

            // Start processing
            const startRes = await fetch('http://localhost:8000/api/start-processing', {
                method: 'POST',
            });

            if (!startRes.ok) throw new Error('Failed to start processing');
            setProgress(100);

            // Navigate to dashboard
            setTimeout(() => navigate('/dashboard'), 500);
        } catch (err) {
            setError(err.message || 'Upload failed. Ensure backend is running on port 8000.');
            setUploading(false);
            setProgress(0);
        }
    };

    const lanes = [
        { key: 'lane1', label: 'Lane 1 Video' },
        { key: 'lane2', label: 'Lane 2 Video' },
        { key: 'lane3', label: 'Lane 3 Video' },
        { key: 'lane4', label: 'Lane 4 Video' },
    ];

    return (
        <div style={{
            minHeight: '100vh',
            background: 'linear-gradient(180deg, #1a1a3e 0%, #2d2d6b 100%)',
            padding: '40px',
            fontFamily: "'Inter', 'Segoe UI', sans-serif",
        }}>
            <div style={{ maxWidth: '700px', margin: '0 auto' }}>
                <h1 style={{ color: '#fff', fontSize: '28px', fontWeight: 700, marginBottom: '8px' }}>
                    Upload Lane Videos
                </h1>
                <p style={{ color: 'rgba(255,255,255,0.6)', marginBottom: '32px', fontSize: '14px' }}>
                    Please upload one video file for each of the four lanes.
                </p>

                {lanes.map(lane => (
                    <div key={lane.key} style={{ marginBottom: '20px' }}>
                        <label style={{ display: 'block', color: '#fff', fontWeight: 600, fontSize: '14px', marginBottom: '8px' }}>
                            {lane.label}:
                        </label>
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: '12px',
                            background: 'rgba(255,255,255,0.08)', borderRadius: '8px', padding: '8px 16px',
                            border: '1px solid rgba(255,255,255,0.15)',
                        }}>
                            <input
                                type="file"
                                accept="video/*"
                                onChange={(e) => handleFileChange(lane.key, e)}
                                style={{ color: '#fff', fontSize: '13px', flex: 1 }}
                            />
                            {files[lane.key] && (
                                <span style={{ color: '#4facfe', fontSize: '12px', whiteSpace: 'nowrap' }}>
                                    {files[lane.key].name}
                                </span>
                            )}
                        </div>
                    </div>
                ))}

                {error && (
                    <div style={{
                        background: 'rgba(255,80,80,0.15)', border: '1px solid rgba(255,80,80,0.3)',
                        borderRadius: '8px', padding: '12px', color: '#ff6b6b', fontSize: '13px',
                        marginBottom: '20px',
                    }}>
                        {error}
                    </div>
                )}

                {/* Progress bar */}
                {uploading && (
                    <div style={{
                        background: 'rgba(255,255,255,0.1)', borderRadius: '8px',
                        overflow: 'hidden', height: '8px', marginBottom: '20px',
                    }}>
                        <div style={{
                            width: `${progress}%`, height: '100%',
                            background: 'linear-gradient(90deg, #4facfe, #00f2fe)',
                            transition: 'width 0.3s ease',
                        }} />
                    </div>
                )}

                <button
                    onClick={handleUpload}
                    disabled={uploading}
                    style={{
                        width: '100%', padding: '16px', borderRadius: '10px', border: 'none',
                        background: uploading
                            ? 'rgba(255,255,255,0.2)'
                            : 'linear-gradient(90deg, #f093fb, #f5576c, #ff9a56)',
                        color: '#fff', fontSize: '16px', fontWeight: 700,
                        cursor: uploading ? 'not-allowed' : 'pointer',
                        transition: 'opacity 0.2s',
                    }}
                >
                    {uploading ? `Uploading... ${progress}%` : 'Upload and Start'}
                </button>

                <button
                    onClick={() => navigate('/')}
                    style={{
                        width: '100%', padding: '12px', borderRadius: '10px',
                        border: '1px solid rgba(255,255,255,0.2)',
                        background: 'transparent', color: 'rgba(255,255,255,0.7)',
                        fontSize: '14px', cursor: 'pointer', marginTop: '12px',
                    }}
                >
                    Back to Home
                </button>
            </div>
        </div>
    );
}
