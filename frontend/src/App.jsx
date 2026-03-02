import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import AnalyticsPage from './pages/AnalyticsPage';

/**
 * App — ITMS Router
 * Routes: Home (/), Upload (/upload), Dashboard (/dashboard), Analysis (/analysis)
 */
export default function App() {
    return (
        <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/analysis" element={<AnalyticsPage />} />
        </Routes>
    );
}
