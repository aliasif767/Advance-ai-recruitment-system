import axios from 'axios';

/**
 * API Base URL resolution:
 *
 * In production (Vercel):
 *   - Set VITE_API_URL in Vercel dashboard → Environment Variables
 *   - e.g. VITE_API_URL = https://your-project.vercel.app/api/v1
 *
 * In local development:
 *   - Falls back to http://localhost:8000/api/v1
 *   - Or set VITE_API_URL=http://localhost:8000/api/v1 in a .env.local file
 *
 * The vite.config.js dev proxy also forwards /api/* → localhost:8000
 * so you can alternatively use just '/api/v1' as the base.
 */
const BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000/api/v1' : '/api/v1');

const api = axios.create({
  baseURL: BASE,
  timeout: 90000,  // 90s — matches Vercel function maxDuration (60s) + buffer
});

api.interceptors.response.use(
  r => r,
  err => {
    const msg = err.response?.data?.detail || err.message || 'Request failed';
    return Promise.reject(new Error(msg));
  }
);

// ── Stats ──────────────────────────────────────────────────────────
export const getGlobalStats = () => api.get('/stats/global').then(r => r.data);

// ── Jobs ───────────────────────────────────────────────────────────
export const listJobs        = (status) => api.get('/jobs/', { params: { status } }).then(r => r.data);
export const getJob          = (id)     => api.get(`/jobs/${id}`).then(r => r.data);
export const createJob       = (data)   => api.post('/jobs/', data, { timeout: 90000 }).then(r => r.data);
export const updateJob       = (id, d)  => api.patch(`/jobs/${id}`, d).then(r => r.data);
export const deleteJob       = (id)     => api.delete(`/jobs/${id}`).then(r => r.data);
export const toggleHiring    = (id)     => api.post(`/jobs/${id}/toggle-hiring`).then(r => r.data);
export const postLinkedIn    = (id)     => api.post(`/jobs/${id}/post-linkedin`).then(r => r.data);

// ── Candidates ─────────────────────────────────────────────────────
export const listCandidates = (params) => api.get('/candidates/', { params }).then(r => r.data);
export const getCandidate   = (id)     => api.get(`/candidates/${id}`).then(r => r.data);
export const updateCandidate = (id, d) => api.patch(`/candidates/${id}`, d).then(r => r.data);
export const deleteCandidate = (id)    => api.delete(`/candidates/${id}`).then(r => r.data);
export const sendEmail       = (id)    => api.post(`/candidates/${id}/send-email`).then(r => r.data);
export const scoreCVFile = (file, jobId) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('job_id', jobId);
  return api.post('/candidates/score/file', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  }).then(r => r.data);
};

// ── Pipeline ───────────────────────────────────────────────────────
export const runPipeline = (data) => api.post('/pipeline/run', data).then(r => r.data);

// ── Assessments ────────────────────────────────────────────────────
export const getAssessmentDashboard = () => api.get('/assessments/dashboard').then(r => r.data);
export const getLiveAssessments     = () => api.get('/assessments/live').then(r => r.data);
export const getAssessment          = (id) => api.get(`/assessments/${id}`).then(r => r.data);
export const getAssessmentReport    = (id) => api.get(`/assessments/${id}/report`).then(r => r.data);
export const createAssessment       = (d)  => api.post('/assessments/create', d).then(r => r.data);
export const getAssessmentViolations= (id) => api.get(`/assessments/${id}/violations`).then(r => r.data);
export const deleteAssessment       = (id) => api.delete(`/assessments/${id}`).then(r => r.data);

// ── Assessment Portal (candidate-facing) ───────────────────────────
export const portalInit    = (token) => api.get(`/assessments/portal/${token}`).then(r => r.data);
export const startSession  = (id)    => api.post(`/assessments/${id}/start`).then(r => r.data);
export const nextQuestion  = (id, sid) => api.get(`/assessments/${id}/session/${sid}/next`).then(r => r.data);
export const submitAnswer  = (id, sid, body) => api.post(`/assessments/${id}/session/${sid}/answer`, body).then(r => r.data);
export const submitAssessment = (id) => api.post(`/assessments/${id}/submit`).then(r => r.data);
export const logViolation = (id, sid, body) => api.post(`/assessments/${id}/session/${sid}/violation`, body).then(r => r.data);

// ── SSE stream (returns an EventSource) ───────────────────────────
// On Vercel production, replace localhost with the same origin
export const SSE_URL = `${BASE.replace('/api/v1', '')}/api/v1/activity/stream`;
