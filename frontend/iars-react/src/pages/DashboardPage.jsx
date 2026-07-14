import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users, Briefcase, CheckCircle, TrendingUp,
  Activity, Radio, ArrowRight, Sparkles
} from 'lucide-react';
import { getGlobalStats } from '../api/client';
import KpiCard      from '../components/ui/KpiCard';
import FunnelChart  from '../components/charts/FunnelChart';
import ActivityFeed from '../components/ui/ActivityFeed';
import ScoreBar     from '../components/ui/ScoreBar';
import Badge        from '../components/ui/Badge';

/* ── Assessment Summary Widget ──────────────────────────────────────── */
function AssessmentSummaryWidget({ stats, loading, onNavigate }) {
  const total     = stats?.total_assessments ?? 0;
  const completed = stats?.completed_assessments ?? 0;
  const inProgress = stats?.in_progress_assessments ?? 0;
  const avgScore  = stats?.avg_assessment_score ?? 0;

  return (
    <div className="card">
      <div className="card-hdr">
        <span className="card-title">
          <span className="dot" style={{ background: 'var(--purple)' }} />
          Assessment Overview
        </span>
        <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('/assessments')}>
          View all <ArrowRight size={12} />
        </button>
      </div>
      <div className="card-body">
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
            <div className="spinner" />
          </div>
        ) : (
          <>
            {/* Mini KPIs */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16 }}>
              {[
                { label: 'Total',    value: total,      color: 'var(--blue)',  bg: 'var(--blue-bg)',   border: 'var(--blue-dim)' },
                { label: 'Done',     value: completed,  color: 'var(--green)', bg: 'var(--green-bg)',  border: 'var(--green-dim)' },
                { label: 'Live',     value: inProgress, color: inProgress > 0 ? 'var(--green)' : 'var(--text3)', bg: 'var(--surface3)', border: 'var(--border2)', live: inProgress > 0 },
              ].map(k => (
                <div key={k.label} style={{ background: k.bg, border: `1px solid ${k.border}`, borderRadius: 10, padding: '12px 14px', textAlign: 'center' }}>
                  <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 22, fontWeight: 700, color: k.color, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, marginBottom: 4 }}>
                    {k.live && <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)', animation: 'pulse 1.5s infinite', display: 'inline-block' }} />}
                    {k.value}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1 }}>{k.label}</div>
                </div>
              ))}
            </div>

            {/* Avg score bar */}
            {avgScore > 0 && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>
                  <span>Avg Assessment Score</span>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontWeight: 600, color: avgScore >= 70 ? 'var(--green)' : avgScore >= 50 ? 'var(--amber)' : 'var(--red)' }}>
                    {avgScore}%
                  </span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{
                    width: `${avgScore}%`,
                    background: avgScore >= 70
                      ? 'linear-gradient(90deg, var(--green-dim), var(--green))'
                      : avgScore >= 50
                      ? 'linear-gradient(90deg, var(--amber-dim), var(--amber))'
                      : 'linear-gradient(90deg, var(--red-dim), var(--red))',
                  }} />
                </div>
              </div>
            )}

            {total === 0 && (
              <div style={{ textAlign: 'center', padding: '8px 0', color: 'var(--text4)', fontSize: 12 }}>
                No assessments sent yet
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/* ── Quick Stats Row ────────────────────────────────────────────────── */
function QuickStatsCard({ stats }) {
  const rows = [
    { label: 'Maybe decisions',      value: stats.maybe_count ?? stats.maybe ?? 0,        color: 'var(--amber)' },
    { label: 'Rejections',           value: stats.reject_count ?? stats.no_match ?? 0,    color: 'var(--red)' },
    { label: 'Interviews scheduled', value: stats.interviews_scheduled ?? stats.interviews ?? 0, color: 'var(--blue)' },
    { label: 'Assessments sent',     value: stats.assessments_sent ?? stats.total_assessments ?? 0, color: 'var(--purple)' },
  ];
  return (
    <div className="card">
      <div className="card-hdr">
        <span className="card-title">
          <span className="dot" style={{ background: 'var(--gold)' }} />
          Quick Stats
        </span>
      </div>
      <div className="card-body" style={{ paddingTop: 14 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {rows.map(row => (
            <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: 'var(--text2)' }}>{row.label}</span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, color: row.color, fontWeight: 600 }}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Top Candidates Card ────────────────────────────────────────────── */
function TopCandidatesCard({ candidates, loading, onNavigate }) {
  return (
    <div className="card">
      <div className="card-hdr">
        <span className="card-title">
          <span className="dot" style={{ background: 'var(--green)' }} />
          Top Candidates
        </span>
        <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('/candidates')}>
          View all <ArrowRight size={12} />
        </button>
      </div>
      <div>
        {loading && (
          <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <div className="skeleton" style={{ width: 28, height: 28, borderRadius: 8, flexShrink: 0 }} />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 5 }}>
                  <div className="skeleton" style={{ height: 12, width: '60%' }} />
                  <div className="skeleton" style={{ height: 10, width: '40%' }} />
                </div>
                <div className="skeleton" style={{ height: 5, width: 80, borderRadius: 3 }} />
              </div>
            ))}
          </div>
        )}
        {!loading && (candidates || []).slice(0, 5).map(c => (
          <div
            key={c.id}
            style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 18px', borderBottom: '1px solid var(--border)', cursor: 'pointer', transition: 'background 0.12s' }}
            onClick={() => onNavigate(`/candidates/${c.id}`)}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div className="avatar avatar-sm">{(c.name || '?')[0].toUpperCase()}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="candidate-name" style={{ fontSize: 13 }}>{c.name}</div>
              <div className="candidate-role">{c.job_title}</div>
            </div>
            <ScoreBar score={c.match_score} />
          </div>
        ))}
        {!loading && !candidates?.length && (
          <div className="empty-state" style={{ padding: 28 }}>
            <div className="empty-state-icon"><Users size={18} /></div>
            <div className="empty-state-title" style={{ fontSize: 13 }}>No candidates yet</div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Page ───────────────────────────────────────────────────────────── */
export default function DashboardPage() {
  const [stats, setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    getGlobalStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const s = stats || {};
  const funnel = [
    { stage: 'Applied', count: s.total_candidates || s.total_cvs || 0 },
    { stage: 'Scored',  count: s.scored            || 0 },
    { stage: 'Match',   count: s.match_count        || s.matched || 0 },
    { stage: 'Hired',   count: s.hired              || 0 },
  ];

  return (
    <>
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Sparkles size={20} style={{ color: 'var(--gold)', opacity: 0.8 }} />
            Dashboard
          </h1>
          <p>Welcome back — here's what's happening with your recruitment pipeline.</p>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="kpi-strip">
        <KpiCard label="Total Candidates" value={loading ? '…' : s.total_candidates ?? s.total_cvs ?? 0}      sub="All time"              accentColor="var(--blue)"   icon={Users} />
        <KpiCard label="Active Jobs"      value={loading ? '…' : s.active_jobs ?? s.total_jobs ?? 0}          sub="Currently open"       accentColor="var(--gold)"   icon={Briefcase} />
        <KpiCard label="Matches"          value={loading ? '…' : s.match_count ?? s.matched ?? 0}             sub="MATCH decision"       accentColor="var(--green)"  icon={CheckCircle} />
        <KpiCard label="Match Rate"       value={loading ? '…' : `${s.match_rate ?? 0}%`}                    sub="Of scored candidates" accentColor="var(--amber)"  icon={TrendingUp} />
        <KpiCard label="Emails Sent"      value={loading ? '…' : s.emails_sent ?? 0}                         sub="Outreach dispatched"  accentColor="var(--purple)" icon={Activity} />
      </div>

      {/* Main grid */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        {/* Funnel chart */}
        <div className="card">
          <div className="card-hdr">
            <span className="card-title">
              <span className="dot" style={{ background: 'var(--blue)' }} />
              Recruitment Funnel
            </span>
            <div className="tabs tabs-pill">
              <button className="tab active">Pipeline</button>
            </div>
          </div>
          <div style={{ padding: '20px 20px 12px' }}>
            <FunnelChart data={funnel} />
          </div>
        </div>

        {/* Right column */}
        <div className="col-r">
          <TopCandidatesCard candidates={s.top_candidates} loading={loading} onNavigate={navigate} />
          <QuickStatsCard stats={s} />
        </div>
      </div>

      {/* Assessment overview */}
      <div style={{ marginBottom: 16 }}>
        <AssessmentSummaryWidget stats={s} loading={loading} onNavigate={navigate} />
      </div>

      {/* Activity feed */}
      <div className="card">
        <div className="card-hdr">
          <span className="card-title">
            <span className="pulse" style={{ color: 'var(--green)' }} />
            Live Activity
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Radio size={12} style={{ color: 'var(--green)' }} />
            <span style={{ fontSize: 11, color: 'var(--text4)', fontFamily: "'DM Mono', monospace" }}>SSE · real-time</span>
          </div>
        </div>
        <ActivityFeed />
      </div>
    </>
  );
}
