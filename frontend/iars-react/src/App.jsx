import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/ui/Toast';
import Layout from './components/layout/Layout';

// Pages
import DashboardPage       from './pages/DashboardPage';
import JobsPage            from './pages/JobsPage';
import JobDetailPage       from './pages/JobDetailPage';
import CandidatesPage      from './pages/CandidatesPage';
import CandidateDetailPage from './pages/CandidateDetailPage';
import PipelinePage        from './pages/PipelinePage';
import AssessmentsPage     from './pages/AssessmentsPage';
import AssessmentReportPage from './pages/AssessmentReportPage';
import AssessmentPortalPage from './pages/AssessmentPortalPage';

export default function App() {
  return (
    <ToastProvider>
      <Router basename="/">
        <Routes>
          {/* Candidate-facing routes (No Layout) */}
          <Route path="/portal/:token" element={<AssessmentPortalPage />} />

          {/* Admin routes (With Layout) */}
          <Route path="/" element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="jobs/:id" element={<JobDetailPage />} />
            <Route path="candidates" element={<CandidatesPage />} />
            <Route path="candidates/:id" element={<CandidateDetailPage />} />
            <Route path="pipeline" element={<PipelinePage />} />
            <Route path="assessments" element={<AssessmentsPage />} />
            <Route path="assessments/:id/report" element={<AssessmentReportPage />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </Router>
    </ToastProvider>
  );
}
