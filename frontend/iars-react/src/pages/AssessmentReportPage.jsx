import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Shield, CheckCircle, XCircle, Brain,
  AlertTriangle, Code2, FileText, BarChart2, Clock,
  Star, Award, TrendingUp, Activity, Copy, Eye,
  Maximize, Lock, ChevronDown, ChevronUp, Bot, FileCheck, HelpCircle
} from 'lucide-react';
import { getAssessmentReport, getAssessmentViolations } from '../api/client';

// ── Score Gauge ────────────────────────────────────────────────────
function ScoreGauge({ score, size = 110 }) {
  const pct = Math.min(score, 100);
  const color = pct >= 70 ? 'var(--green)' : pct >= 50 ? 'var(--amber)' : 'var(--red)';
  const r = 44;
  const circ = 2 * Math.PI * r;
  const dash = (pct / 100) * circ;

  return (
    <div style={{ position: 'relative', width: size, height: size, margin: '0 auto' }}>
      <svg width={size} height={size} viewBox="0 0 100 100" style={{ transform: 'rotate(-90deg)', overflow: 'visible' }}>
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--surface3)" strokeWidth="6" />
        <circle
          cx="50" cy="50" r={r} fill="none" stroke={color} strokeWidth="6"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 1.2s cubic-bezier(0.34, 1.56, 0.64, 1)' }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center'
      }}>
        <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 28, fontWeight: 700, color, lineHeight: 1 }}>
          {pct?.toFixed(0)}<span style={{ fontSize: 14 }}>%</span>
        </div>
      </div>
    </div>
  );
}

// ── Section Score Bar ──────────────────────────────────────────────
function SectionBar({ label, score, max = 100, weight, color }) {
  const pct = score != null ? Math.min((score / max) * 100, 100) : 0;
  const c = color || (pct >= 70 ? 'var(--green)' : pct >= 50 ? 'var(--amber)' : 'var(--red)');
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{label}</span>
          {weight && <span className="badge" style={{ background: 'var(--surface3)', color: 'var(--text3)' }}>{weight}%</span>}
        </div>
        <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, color: c, fontWeight: 600 }}>
          {score != null ? `${score.toFixed(1)}%` : '—'}
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--surface3)', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: c, borderRadius: 4, transition: 'width 1s cubic-bezier(0.34, 1.56, 0.64, 1)' }} />
      </div>
    </div>
  );
}

// ── Recommendation Card ────────────────────────────────────────────
function RecommendationCard({ rec, confidence }) {
  const map = {
    strongly_hire: { icon: Star, label: 'Strongly Hire', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-dim)', desc: 'Exceptional candidate — fast-track for offer' },
    hire:          { icon: CheckCircle, label: 'Hire', color: 'var(--green)', bg: 'var(--green-bg)', border: 'var(--green-dim)', desc: 'Strong candidate — proceed to next round' },
    maybe:         { icon: HelpCircle, label: 'Maybe', color: 'var(--amber)', bg: 'var(--amber-bg)', border: 'var(--amber-dim)', desc: 'Borderline — consider a follow-up interview' },
    reject:        { icon: XCircle, label: 'Reject', color: 'var(--red)', bg: 'var(--red-bg)', border: 'var(--red-dim)', desc: 'Does not meet requirements at this stage' },
  };
  const m = map[rec] || { icon: Clock, label: rec || 'Pending', color: 'var(--text2)', bg: 'var(--surface3)', border: 'var(--border)', desc: 'Evaluation in progress…' };
  const Icon = m.icon;

  return (
    <div style={{ background: m.bg, border: `1px solid ${m.border}`, borderRadius: 12, padding: '20px 24px', display: 'flex', alignItems: 'center', gap: 20 }}>
      <div style={{ color: m.color }}><Icon size={32} /></div>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: "'Fraunces', serif", fontSize: 20, fontWeight: 300, color: m.color, marginBottom: 4 }}>
          {m.label}
        </div>
        <div style={{ fontSize: 13, color: 'var(--text2)' }}>{m.desc}</div>
      </div>
      {confidence != null && (
        <div style={{ textAlign: 'center', borderLeft: `1px solid ${m.border}`, paddingLeft: 24 }}>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 24, fontWeight: 700, color: m.color }}>{confidence}%</div>
          <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1 }}>confidence</div>
        </div>
      )}
    </div>
  );
}

// ── Answer Row ─────────────────────────────────────────────────────
function AnswerRow({ answer, index }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = typeof answer.answer === 'string' && answer.answer.length > 120;

  return (
    <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{
          width: 24, height: 24, borderRadius: '50%', flexShrink: 0, marginTop: 2,
          background: answer.is_correct ? 'var(--green-bg)' : answer.skipped ? 'var(--surface3)' : 'var(--red-bg)',
          border: `1px solid ${answer.is_correct ? 'var(--green-dim)' : answer.skipped ? 'var(--border)' : 'var(--red-dim)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          {answer.is_correct
            ? <CheckCircle size={14} style={{ color: 'var(--green)' }} />
            : answer.skipped
            ? <span style={{ fontSize: 10, color: 'var(--text3)' }}>—</span>
            : <XCircle size={14} style={{ color: 'var(--red)' }} />}
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13.5, fontWeight: 500, marginBottom: 8, color: 'var(--text)', lineHeight: 1.5 }}>
            <span style={{ color: 'var(--text4)', fontFamily: "'DM Mono', monospace", marginRight: 8, fontWeight: 600 }}>Q{index + 1}</span>
            {answer.question_text || `Question ${index + 1}`}
          </div>

          {answer.answer != null && !answer.skipped && (
            <div style={{ position: 'relative' }}>
              <div style={{
                fontSize: 13, color: 'var(--text2)', background: 'var(--surface2)',
                border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px',
                fontFamily: answer.question_type === 'coding' ? "'DM Mono', monospace" : 'inherit',
                overflow: 'hidden',
                maxHeight: expanded ? 'none' : isLong ? 72 : 'none',
                WebkitLineClamp: expanded ? 'none' : 3,
                display: '-webkit-box',
                WebkitBoxOrient: 'vertical',
                transition: 'max-height 0.3s ease',
                lineHeight: 1.6
              }}>
                {String(answer.answer)}
              </div>
              {isLong && (
                <button
                  onClick={() => setExpanded(e => !e)}
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'var(--gold)', padding: '4px 0', marginTop: 4, height: 'auto' }}
                >
                  {expanded ? <><ChevronUp size={14} /> Show less</> : <><ChevronDown size={14} /> Show full answer</>}
                </button>
              )}
            </div>
          )}
          {answer.skipped && (
            <div style={{ fontSize: 12, color: 'var(--text4)', fontStyle: 'italic', padding: '8px 12px', background: 'var(--surface2)', borderRadius: 8 }}>Skipped by candidate</div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
          {answer.score != null && (
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: 'var(--gold)', fontWeight: 600 }}>
              {answer.score} pts
            </span>
          )}
          {answer.time_taken_seconds != null && (
            <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
              {answer.time_taken_seconds}s
            </span>
          )}
          {answer.question_type && (
            <span className="badge" style={{ background: 'var(--surface3)', color: 'var(--text3)' }}>
              {answer.question_type}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Violation Log ──────────────────────────────────────────────────
function ViolationLog({ violations }) {
  if (!violations) return <div style={{ color: 'var(--text3)', fontSize: 13 }}>No proctoring data available for this session.</div>;

  const severityColor = { low: 'var(--text3)', medium: 'var(--amber)', high: 'var(--red)', critical: 'var(--red)' };
  const vList = violations.violations || [];

  return (
    <div>
      <div className="grid-2-equal" style={{ gap: 12, marginBottom: 20 }}>
        {Object.entries(violations.by_type || {}).map(([type, count]) => (
          <div key={type} className="card" style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 0 }}>
            <span style={{ fontSize: 13, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 8 }}>
              {type === 'tabSwitch' || type === 'tab_switch' ? <Eye size={14} style={{color: 'var(--blue)'}} /> :
               type === 'copyPaste' || type === 'copy_attempt' || type === 'paste_attempt' ? <Copy size={14} style={{color: 'var(--amber)'}} /> :
               type === 'fullscreenExit' || type === 'fullscreen_exit' ? <Maximize size={14} style={{color: 'var(--purple)'}} /> :
               <Lock size={14} style={{color: 'var(--red)'}} />}
              {type.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').trim()}
            </span>
            <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, fontWeight: 600, color: count >= 3 ? 'var(--red)' : count >= 1 ? 'var(--amber)' : 'var(--text3)' }}>{count}</span>
          </div>
        ))}
        {!Object.keys(violations.by_type || {}).length && (
          <div style={{ gridColumn: '1/-1', background: 'var(--green-bg)', color: 'var(--green)', border: '1px solid var(--green-dim)', borderRadius: 10, padding: 16, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircle size={16} /> No violations detected. Honest test-taking behavior confirmed.
          </div>
        )}
      </div>

      {violations.cheating_penalty > 0 && (
        <div style={{ background: 'var(--red-bg)', border: '1px solid var(--red-dim)', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, color: 'var(--red)', display: 'flex', alignItems: 'center', gap: 8 }}><AlertTriangle size={16} /> Cheating Penalty Applied</span>
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 18, fontWeight: 700, color: 'var(--red)' }}>
            -{violations.cheating_penalty} pts
          </span>
        </div>
      )}

      {violations.high_risk && (
        <div style={{ background: 'var(--red-bg)', border: '1px solid var(--red-dim)', borderRadius: 10, padding: '16px 20px', marginBottom: 20, display: 'flex', alignItems: 'center', gap: 10 }}>
          <AlertTriangle size={18} style={{ color: 'var(--red)', flexShrink: 0 }} />
          <span style={{ fontSize: 13.5, color: 'var(--red)', fontWeight: 500 }}>High-risk candidate — multiple severe violations detected during the session.</span>
        </div>
      )}

      {vList.length > 0 && (
        <div>
          <div className="section-title">Violation Timeline</div>
          <div style={{ maxHeight: 300, overflowY: 'auto', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
            {vList.map((v, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '10px 12px', borderBottom: i === vList.length - 1 ? 'none' : '1px solid var(--border2)' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: severityColor[v.severity] || 'var(--text3)', marginTop: 6, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--text)' }}>{v.description || v.type}</div>
                  <div style={{ fontSize: 11, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", marginTop: 4 }}>
                    {v.logged_at ? new Date(v.logged_at).toLocaleTimeString() : ''}
                  </div>
                </div>
                <Badge label={v.severity} variant={v.severity === 'high' || v.severity === 'critical' ? 'REJECT' : v.severity === 'medium' ? 'MAYBE' : 'PENDING'} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


export default function AssessmentReportPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  const [violations, setViolations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    Promise.all([getAssessmentReport(id), getAssessmentViolations(id)])
      .then(([r, v]) => { setReport(r); setViolations(v); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;

  if (!report) return (
    <div className="empty-state" style={{ padding: 80 }}>
      <div className="empty-state-icon"><BarChart2 size={24} /></div>
      <div className="empty-state-title">Report Not Ready</div>
      <div className="empty-state-sub">Assessment may still be in progress or pending AI evaluation</div>
      <button className="btn btn-ghost" style={{ marginTop: 24 }} onClick={() => navigate('/assessments')}>
        <ArrowLeft size={14} /> Back to Assessments
      </button>
    </div>
  );

  const r = report;
  const finalScore = r.final_composite_score ?? r.final_score ?? 0;
  const answers = r.answers || [];
  const correctCount = answers.filter(a => a.is_correct).length;

  const tabs = [
    { key: 'overview', label: 'Overview', icon: BarChart2 },
    { key: 'answers', label: `Answers (${answers.length})`, icon: FileCheck },
    { key: 'proctoring', label: 'Proctoring', icon: Shield },
    { key: 'ai', label: 'AI Deep Dive', icon: Bot },
  ];

  return (
    <>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 32 }}>
        <button className="btn btn-ghost btn-icon" onClick={() => navigate('/assessments')}><ArrowLeft size={16} /></button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontFamily: "'Inter', sans-serif", fontSize: 24, fontWeight: 600, letterSpacing: '-0.5px' }}>Assessment Report</h1>
          <div style={{ fontSize: 13.5, color: 'var(--text3)', marginTop: 4 }}>
            {r.candidate_name} · {r.job_title} · {r.company}
          </div>
        </div>
        <div style={{ textAlign: 'right', background: 'var(--surface2)', padding: '12px 20px', borderRadius: 12, border: '1px solid var(--border)' }}>
          <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 32, lineHeight: 1, color: finalScore >= 70 ? 'var(--green)' : finalScore >= 50 ? 'var(--amber)' : 'var(--red)', fontWeight: 700 }}>
            {finalScore?.toFixed(1)}%
          </div>
          <div style={{ fontSize: 10, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", letterSpacing: 1, marginTop: 6 }}>FINAL SCORE</div>
        </div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <RecommendationCard rec={r.recommendation} confidence={r.hiring_confidence} />
      </div>

      {/* Stats Strip */}
      <div className="kpi-strip" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: 32 }}>
        {[
          { label: 'MCQ Score', val: r.mcq_score != null ? `${r.mcq_score?.toFixed(1)}%` : '—', color: 'var(--blue)', icon: FileText },
          { label: 'Code Score', val: r.coding_score != null ? `${r.coding_score?.toFixed(1)}%` : '—', color: 'var(--purple)', icon: Code2 },
          { label: 'Answers', val: `${correctCount}/${answers.length}`, color: 'var(--green)', icon: CheckCircle },
          { label: 'Violations', val: violations?.total_violations ?? '—', color: violations?.total_violations > 0 ? 'var(--red)' : 'var(--green)', icon: Shield },
          { label: 'Overall Rating', val: r.overall_rating ? `${r.overall_rating}/5` : '—', color: 'var(--gold)', icon: Star },
        ].map(k => (
          <div key={k.label} className="card" style={{ padding: '20px 16px', textAlign: 'center', marginBottom: 0 }}>
            <div style={{ color: k.color, marginBottom: 12, display: 'flex', justifyContent: 'center' }}><k.icon size={20} /></div>
            <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 20, fontWeight: 700, color: 'var(--text)', marginBottom: 4 }}>{k.val}</div>
            <div style={{ fontSize: 11, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="tabs tabs-pill" style={{ marginBottom: 24 }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`tab ${activeTab === tab.key ? 'active' : ''}`}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <tab.icon size={14} /> {tab.label}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ── */}
      {activeTab === 'overview' && (
        <div className="grid-2">
          <div className="col-r">
            <div className="card">
              <div className="card-hdr"><span className="card-title"><BarChart2 size={16} /> Score Breakdown</span></div>
              <div className="card-body">
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 32 }}>
                  <ScoreGauge score={finalScore} />
                </div>
                <SectionBar label="MCQ / Knowledge" score={r.mcq_score} weight={25} color="var(--blue)" />
                <SectionBar label="Coding / Technical" score={r.coding_score} weight={30} color="var(--purple)" />
                <SectionBar label="Short Answers" score={r.short_answer_score} weight={20} color="var(--green)" />
                <SectionBar label="Communication" score={r.communication_score} weight={10} />
                <SectionBar label="Problem Solving" score={r.problem_solving_score} weight={15} color="var(--gold)" />
              </div>
            </div>
          </div>

          <div className="col-r">
            {r.candidate_summary && (
              <div className="card">
                <div className="card-hdr"><span className="card-title"><Bot size={16} /> AI Summary</span></div>
                <div className="card-body">
                  <p style={{ fontSize: 13.5, color: 'var(--text2)', lineHeight: 1.7 }}>{r.candidate_summary}</p>
                </div>
              </div>
            )}

            {(r.strengths?.length || r.weaknesses?.length) && (
              <div className="card">
                <div className="card-hdr"><span className="card-title"><TrendingUp size={16} /> Strengths & Gaps</span></div>
                <div className="card-body">
                  {r.strengths?.length > 0 && (
                    <div style={{ marginBottom: 20 }}>
                      <div className="section-title" style={{ color: 'var(--green)' }}>Strengths</div>
                      {r.strengths.map((s, i) => (
                        <div key={i} style={{ display: 'flex', gap: 10, fontSize: 13.5, color: 'var(--text2)', marginBottom: 8, lineHeight: 1.5 }}>
                          <CheckCircle size={14} style={{ color: 'var(--green)', flexShrink: 0, marginTop: 2 }} /> {s}
                        </div>
                      ))}
                    </div>
                  )}
                  {r.weaknesses?.length > 0 && (
                    <div>
                      <div className="section-title" style={{ color: 'var(--amber)' }}>Areas for Improvement</div>
                      {r.weaknesses.map((w, i) => (
                        <div key={i} style={{ display: 'flex', gap: 10, fontSize: 13.5, color: 'var(--text2)', marginBottom: 8, lineHeight: 1.5 }}>
                          <XCircle size={14} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: 2 }} /> {w}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Answers Tab ── */}
      {activeTab === 'answers' && (
        <div className="card">
          <div className="card-hdr">
            <span className="card-title"><FileCheck size={16} /> Question Results</span>
            <span style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
              {correctCount}/{answers.length} correct
            </span>
          </div>
          {answers.length === 0 ? (
            <div className="empty-state" style={{ padding: 60 }}>
              <div className="empty-state-icon"><FileCheck size={24} /></div>
              <div className="empty-state-title">No answers recorded</div>
            </div>
          ) : (
            answers.map((a, i) => <AnswerRow key={i} answer={a} index={i} />)
          )}
        </div>
      )}

      {/* ── Proctoring Tab ── */}
      {activeTab === 'proctoring' && (
        <div className="card">
          <div className="card-hdr">
            <span className="card-title"><Shield size={16} /> Proctoring Report</span>
          </div>
          <div className="card-body">
            <ViolationLog violations={violations} />
          </div>
        </div>
      )}

      {/* ── AI Analysis Tab ── */}
      {activeTab === 'ai' && (
        <div className="grid-2-equal">
          {[
            { label: 'Technical Analysis', val: r.technical_analysis, icon: Code2 },
            { label: 'Communication', val: r.communication_assessment, icon: FileText },
            { label: 'Coding Performance', val: r.coding_performance, icon: Code2 },
            { label: 'Soft Skills', val: r.soft_skills_analysis, icon: Brain },
            { label: 'Risk Analysis', val: r.risk_analysis, icon: AlertTriangle },
            { label: 'Cheating Summary', val: r.cheating_summary, icon: Shield },
          ].filter(s => s.val).map(section => (
            <div key={section.label} className="card">
              <div className="card-hdr">
                <span className="card-title"><section.icon size={16} /> {section.label}</span>
              </div>
              <div className="card-body">
                <p style={{ fontSize: 13.5, color: 'var(--text2)', lineHeight: 1.7 }}>{section.val}</p>
              </div>
            </div>
          ))}
          {![r.technical_analysis, r.communication_assessment, r.coding_performance, r.soft_skills_analysis].some(Boolean) && (
            <div className="empty-state" style={{ gridColumn: '1/-1', padding: 80 }}>
              <div className="empty-state-icon"><Bot size={32} /></div>
              <div className="empty-state-title">AI Analysis Pending</div>
              <div className="empty-state-sub">The AI evaluation is still processing the responses.</div>
            </div>
          )}
        </div>
      )}
    </>
  );
}
