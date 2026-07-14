import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity, Clock, CheckCircle, AlertTriangle, TrendingUp,
  Award, RefreshCw, BarChart2, Trash2, ClipboardList
} from 'lucide-react';
import { getAssessmentDashboard, getLiveAssessments, deleteAssessment } from '../api/client';
import Badge from '../components/ui/Badge';
import KpiCard from '../components/ui/KpiCard';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/Toast';

// ── Mini Score Bar ─────────────────────────────────────────────────
function ScoreBarMini({ score, max = 100, color }) {
  const pct = Math.min((score / max) * 100, 100);
  const c = color || (score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--amber)' : 'var(--red)');
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <div style={{ flex: 1, height: 5, background: 'var(--surface3)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: c, borderRadius: 3, transition: 'width 0.6s ease' }} />
      </div>
      <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 11.5, color: c, minWidth: 36, textAlign: 'right', fontWeight: 600 }}>
        {score != null ? `${score}%` : '—'}
      </span>
    </div>
  );
}

// ── Score Distribution Mini Chart ──────────────────────────────────
function ScoreDistChart({ data }) {
  const labels = ['0–20', '20–40', '40–60', '60–80', '80–100'];
  const colors = ['var(--red)', 'var(--amber)', 'var(--amber)', 'var(--green)', 'var(--green)'];
  const max = Math.max(...data, 1);
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8, height: 64, padding: '0 8px' }}>
      {data.map((val, i) => (
        <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", fontWeight: 500 }}>{val}</div>
          <div style={{
            width: '100%',
            height: `${(val / max) * 44}px`,
            minHeight: val > 0 ? 4 : 0,
            background: colors[i],
            borderRadius: '4px 4px 0 0',
            transition: 'height 0.5s ease',
          }} />
          <div style={{ fontSize: 9.5, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", textAlign: 'center', letterSpacing: -0.5 }}>{labels[i]}</div>
        </div>
      ))}
    </div>
  );
}

// ── Status Badge ───────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = {
    pending:   { label: 'Pending', color: 'var(--text3)', bg: 'var(--surface3)', border: 'var(--border)', dot: false },
    active:    { label: 'Live', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-dim)', dot: true },
    submitted: { label: 'Submitted', color: 'var(--blue)', bg: 'var(--blue-bg)', border: 'var(--blue-dim)', dot: false },
    evaluated: { label: 'Evaluated', color: 'var(--gold)', bg: 'var(--gold-bg)', border: 'var(--gold-dim)', dot: false },
    expired:   { label: 'Expired', color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red-dim)', dot: false },
  };
  const m = map[status] || { label: status, color: 'var(--text2)', bg: 'var(--surface3)', border: 'var(--border)' };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11.5, fontWeight: 500, padding: '4px 10px', borderRadius: 20, background: m.bg, border: `1px solid ${m.border}`, color: m.color, fontFamily: "'DM Mono', monospace" }}>
      {m.dot && <span className="pulse" style={{ width: 6, height: 6, background: m.color }} />}
      {m.label}
    </span>
  );
}

export default function AssessmentsPage() {
  const [stats, setStats] = useState(null);
  const [live, setLive] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('all');
  const [confirm, setConfirm] = useState({ open: false, id: null });
  
  const navigate = useNavigate();
  const toast = useToast();

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const [s, l] = await Promise.all([getAssessmentDashboard(), getLiveAssessments()]);
      setStats(s);
      setLive(l);
    } catch (e) { 
      toast.error('Failed to load assessments'); 
    } finally { 
      setLoading(false); 
      setRefreshing(false); 
    }
  }, [toast]);

  useEffect(() => {
    load();
    const iv = setInterval(() => getLiveAssessments().then(setLive).catch(() => {}), 20000);
    return () => clearInterval(iv);
  }, [load]);

  const s = stats || {};
  const allAssessments = s.assessments || [];
  const filtered = filter === 'all' ? allAssessments : allAssessments.filter(a => a.status === filter);

  const filters = [
    { key: 'all',       label: 'All' },
    { key: 'active',    label: 'Live' },
    { key: 'evaluated', label: 'Evaluated' },
    { key: 'submitted', label: 'Submitted' },
    { key: 'pending',   label: 'Pending' },
  ];

  const handleDelete = async () => {
    try {
      await deleteAssessment(confirm.id);
      toast.success('Assessment deleted');
      load(); 
    } catch (err) {
      toast.error('Failed to delete assessment');
    } finally {
      setConfirm({ open: false, id: null });
    }
  };

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Assessments</h1>
          <p>Track candidate test results and AI proctoring</p>
        </div>
        <div className="page-header-actions">
          <button
            className="btn btn-surface"
            onClick={() => load(true)}
            disabled={refreshing}
          >
            <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            Refresh Data
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="kpi-strip">
        <KpiCard label="Total Given" value={loading ? '…' : s.total ?? 0} accentColor="var(--blue)" icon={Activity} />
        <KpiCard label="Evaluated"   value={loading ? '…' : s.evaluated ?? 0} accentColor="var(--gold)" icon={Award} />
        <KpiCard label="In Progress" value={loading ? '…' : s.active ?? 0} accentColor="var(--green)" icon={Clock} dot={s.active > 0} />
        <KpiCard label="Avg Score"   value={loading ? '…' : s.avg_score ? `${s.avg_score}%` : '—'} accentColor="var(--purple)" icon={TrendingUp} />
        <KpiCard label="Pass Rate"   value={loading ? '…' : s.pass_rate ? `${s.pass_rate}%` : '—'} accentColor="var(--amber)" icon={CheckCircle} />
      </div>

      <div className="grid-2-equal" style={{ marginBottom: 20 }}>
        {/* Score distribution */}
        <div className="card">
          <div className="card-hdr">
            <span className="card-title"><BarChart2 size={16} /> Score Distribution</span>
            <span style={{ fontSize: 11.5, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
              {s.pass_count || 0} passed ≥60%
            </span>
          </div>
          <div className="card-body" style={{ padding: '24px 24px 16px' }}>
            {loading ? (
              <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><div className="spinner" /></div>
            ) : (
              <ScoreDistChart data={s.score_distribution || [0, 0, 0, 0, 0]} />
            )}
          </div>
        </div>

        {/* Status summary */}
        <div className="card">
          <div className="card-hdr">
            <span className="card-title"><Activity size={16} /> Status Breakdown</span>
          </div>
          <div className="card-body" style={{ paddingTop: 16 }}>
            {[
              { label: 'Pending',   val: s.pending || 0, color: 'var(--text3)' },
              { label: 'Active',    val: s.active || 0,  color: 'var(--green)' },
              { label: 'Submitted', val: s.submitted || 0, color: 'var(--blue)' },
              { label: 'Evaluated', val: s.evaluated || 0, color: 'var(--gold)' },
              { label: 'Expired',   val: s.expired || 0, color: 'var(--red)' },
            ].map(row => (
              <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: row.color }} />
                  <span style={{ fontSize: 13, color: 'var(--text2)' }}>{row.label}</span>
                </div>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, color: row.color, fontWeight: 600 }}>{row.val}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Live sessions */}
      {live.length > 0 && (
        <div className="card" style={{ marginBottom: 20, border: '1px solid var(--green-dim)', boxShadow: '0 0 0 1px rgba(34,197,94,0.1)' }}>
          <div className="card-hdr" style={{ background: 'var(--green-bg)' }}>
            <span className="card-title" style={{ color: 'var(--green)' }}>
              <span className="pulse" style={{ background: 'var(--green)', width: 8, height: 8, marginRight: 6 }} />
              Live Sessions ({live.length})
            </span>
            <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>auto-refreshes</span>
          </div>
          <div>
            {live.map(a => (
              <div
                key={a.session_id || a.assessment_id}
                style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}
                onClick={() => navigate(`/assessments/${a.assessment_id}/report`)}
                className="activity-item"
              >
                <div className="avatar avatar-sm">{(a.candidate_name || '?')[0].toUpperCase()}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text)' }}>{a.candidate_name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text3)' }}>{a.job_title}</div>
                </div>
                <div style={{ textAlign: 'center', minWidth: 64 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'DM Mono', monospace" }}>{a.progress}</div>
                  <div style={{ fontSize: 10.5, color: 'var(--text4)', textTransform: 'uppercase' }}>Questions</div>
                </div>
                {a.time_remaining != null && (
                  <div style={{ textAlign: 'center', minWidth: 64 }}>
                    <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: a.time_remaining < 300 ? 'var(--red)' : 'var(--text)' }}>
                      {Math.floor(a.time_remaining / 60)}:{String(a.time_remaining % 60).padStart(2, '0')}
                    </div>
                    <div style={{ fontSize: 10.5, color: 'var(--text4)', textTransform: 'uppercase' }}>Time Left</div>
                  </div>
                )}
                <div style={{ textAlign: 'center', minWidth: 64 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, fontFamily: "'DM Mono', monospace", color: a.violations > 0 ? 'var(--red)' : 'var(--green)' }}>
                    {a.violations || 0}
                  </span>
                  <div style={{ fontSize: 10.5, color: 'var(--text4)', textTransform: 'uppercase' }}>Violations</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All assessments table */}
      <div className="card">
        <div className="card-hdr">
          <span className="card-title">Assessment History</span>
          <div className="tabs tabs-pill">
            {filters.map(f => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`tab ${filter === f.key ? 'active' : ''}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Role</th>
                <th>Status</th>
                <th>Score</th>
                <th style={{ width: 220 }}>Sections</th>
                <th>Verdict</th>
                <th>Submitted</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 60 }}><div className="spinner" /></td></tr>
              )}
              
              {!loading && filtered.length === 0 && (
                <tr><td colSpan={8}>
                  <div className="empty-state">
                    <div className="empty-state-icon"><ClipboardList size={24} /></div>
                    <div className="empty-state-title">No assessments</div>
                    <div className="empty-state-sub">No results match this filter</div>
                  </div>
                </td></tr>
              )}
              
              {filtered.map(a => (
                <tr key={a.id} onClick={() => navigate(`/assessments/${a.id}/report`)}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <div className="avatar avatar-sm">{(a.candidate_name || '?')[0].toUpperCase()}</div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13.5, color: 'var(--text)' }}>{a.candidate_name || '—'}</div>
                        <div style={{ fontSize: 11.5, color: 'var(--text4)' }}>{a.candidate_email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 500, fontSize: 13, color: 'var(--text2)' }}>{a.job_title || '—'}</div>
                  </td>
                  <td><StatusBadge status={a.status} /></td>
                  <td>
                    {a.final_score != null ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 18, fontWeight: 700, color: a.final_score >= 70 ? 'var(--green)' : a.final_score >= 50 ? 'var(--amber)' : 'var(--red)' }}>
                          {a.final_score}%
                        </span>
                        {a.cheating_penalty > 0 && <span className="badge badge-reject">-{a.cheating_penalty} pts</span>}
                      </div>
                    ) : <span style={{ color: 'var(--text4)' }}>—</span>}
                  </td>
                  <td>
                    {(a.mcq_score != null || a.coding_score != null) ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {a.mcq_score != null && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 10, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", width: 28 }}>MCQ</span>
                            <ScoreBarMini score={a.mcq_score} />
                          </div>
                        )}
                        {a.coding_score != null && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 10, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", width: 28 }}>DEV</span>
                            <ScoreBarMini score={a.coding_score} color="var(--purple)" />
                          </div>
                        )}
                      </div>
                    ) : <span style={{ color: 'var(--text4)' }}>—</span>}
                  </td>
                  <td>
                    {a.recommendation ? (
                      <Badge 
                        label={a.recommendation.replace('_', ' ').toUpperCase()} 
                        variant={a.recommendation === 'strongly_hire' || a.recommendation === 'hire' ? 'MATCH' : a.recommendation === 'maybe' ? 'MAYBE' : 'REJECT'} 
                      />
                    ) : <span style={{ color: 'var(--text4)' }}>—</span>}
                  </td>
                  <td>
                    <span style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
                      {a.submitted_at ? new Date(a.submitted_at).toLocaleDateString() : '—'}
                    </span>
                  </td>
                  <td>
                    <button 
                      className="btn btn-ghost btn-sm btn-icon" 
                      style={{ color: 'var(--text4)' }} 
                      onClick={(e) => { e.stopPropagation(); setConfirm({ open: true, id: a.id }); }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={confirm.open}
        title="Delete Assessment"
        message="This will delete the assessment, all test answers, and the proctoring report."
        confirmLabel="Delete"
        onConfirm={handleDelete}
        onCancel={() => setConfirm({ open: false, id: null })}
      />
    </>
  );
}
