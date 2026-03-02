/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            /* Government Command Center color system */
            colors: {
                panel: {
                    bg: '#0a0e17',
                    surface: '#111827',
                    card: '#1a2332',
                    border: '#2a3548',
                    hover: '#243044',
                },
                status: {
                    green: '#22c55e',
                    amber: '#f59e0b',
                    red: '#ef4444',
                    blue: '#3b82f6',
                },
                text: {
                    primary: '#e5e7eb',
                    secondary: '#9ca3af',
                    muted: '#6b7280',
                    heading: '#f9fafb',
                },
            },
            fontFamily: {
                mono: ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
                sans: ['"Inter"', '"Segoe UI"', 'system-ui', 'sans-serif'],
            },
            fontSize: {
                '2xs': ['0.65rem', { lineHeight: '0.85rem' }],
            },
        },
    },
    plugins: [],
}
