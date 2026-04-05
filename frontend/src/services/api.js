// frontend/src/services/api.js
// Central API service — all backend calls go through here

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

async function req(method, path, body = null, isForm = false) {
  const opts = {
    method,
    headers: isForm ? {} : { "Content-Type": "application/json" },
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  };
  const res = await fetch(`${BASE}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

// ── Stats ─────────────────────────────────────────────────────────────────────
export const statsApi = {
  global: () => req("GET", "/stats/global"),
};

// ── Activity ──────────────────────────────────────────────────────────────────
export const activityApi = {
  list: (limit = 30) => req("GET", `/activity/?limit=${limit}`),
};

// ── Jobs ──────────────────────────────────────────────────────────────────────
export const jobsApi = {
  list:         (status)     => req("GET", `/jobs/${status ? `?status=${status}` : ""}`),
  get:          (id)         => req("GET", `/jobs/${id}`),
  create:       (data)       => req("POST", "/jobs/", data),
  update:       (id, data)   => req("PATCH", `/jobs/${id}`, data),
  postLinkedIn: (id)         => req("POST", `/jobs/${id}/post-linkedin`),
};

// ── Candidates ────────────────────────────────────────────────────────────────
export const candidatesApi = {
  list: (params = {}) => {
    const q = new URLSearchParams(params).toString();
    return req("GET", `/candidates/${q ? `?${q}` : ""}`);
  },
  get:          (id)          => req("GET", `/candidates/${id}`),
  scoreText:    (data)        => req("POST", "/candidates/score/text", data),
  scoreFile:    (file, jobId) => {
    const form = new FormData();
    form.append("file", file);
    form.append("job_id", jobId);
    return req("POST", "/candidates/score/file", form, true);
  },
  update:       (id, data)    => req("PATCH", `/candidates/${id}`, data),
  delete:       (id)          => req("DELETE", `/candidates/${id}`),
  sendEmail:    (id)          => req("POST", `/candidates/${id}/send-email`),
};

// ── Pipeline ──────────────────────────────────────────────────────────────────
export const pipelineApi = {
  run:       (data) => req("POST", "/pipeline/run", data),
  scoreOnly: (data) => req("POST", "/pipeline/score-only", data),
  runs:      (limit = 20) => req("GET", `/pipeline/runs?limit=${limit}`),
};

// ── SSE Activity Stream ───────────────────────────────────────────────────────
export function subscribeToActivity(onEvent) {
  const url = `${BASE}/activity/stream`;
  const es = new EventSource(url);
  es.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)); } catch (_) {}
  };
  es.onerror = () => es.close();
  return () => es.close(); // cleanup fn
}
