import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Mail, Code, GraduationCap, Calendar, Send, Trash2, GitBranch, Link } from 'lucide-react';
import { getCandidate, sendEmail, deleteCandidate, createAssessment, listJobs } from '../api/client';
import Badge from '../components/ui/Badge';
import ScoreBar from '../components/ui/ScoreBar';
import ScoreRadarChart from '../components/charts/ScoreRadarChart';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/Toast';

export default function CandidateDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [candidate, setCandidate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [tab, setTab] = useState('overview');
  const [showAssess, setShowAssess] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [assessJobId, setAssessJobId] = useState('');
  const [creating, setCreating] = useState(false);
  const [assessResult, setAssessResult] = useState(null);
  const [confirm, setConfirm] = useState({ open: false });
  const toast = useToast();

  useEffect(() => {
    getCandidate(id).then(setCandidate).catch(console.error).finally(() => setLoading(false));
    listJobs().then(j => { setJobs(j); if (j.length) setAssessJobId(j[0].id); }).catch(console.error);
  }, [id]);

  const handleSendEmail = async () => {
    setSending(true);
    try {
      await sendEmail(id);
      setCandidate(prev => ({ ...prev, email_sent: true }));
      toast.success('Email sent successfully to ' + candidate.name);
    } catch (e) { 
      toast.error('Failed to send email: ' + e.message); 
    } finally { 
      setSending(false); 
    }
  };

  const handleDelete = async () => {
    try {
      await deleteCandidate(id);
      toast.success('Candidate deleted');
      navigate('/candidates');
    } catch (e) {
      toast.error('Failed to delete candidate');
    }
  };

  const handleCreateAssessment = async () => {
    setCreating(true);
    try {
      const res = await createAssessment({ candidate_id: id, job_id: assessJobId, resume_score: candidate.match_score || 0 });
      setAssessResult(res);
      toast.success('Assessment created');
    } catch (e) { 
      toast.error('Failed to create assessment: ' + e.message); 
    } finally { 
      setCreating(false); 
    }
  };

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;
  if (!candidate) return <div className="empty-state"><div className="empty-state-title">Candidate not found</div></div>;

  const c = candidate;
  const scores = c.evaluation_scores || {};

  return (
    <>
      {/* Header Profile Hero */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 20, marginBottom: 32 }}>
        <button className="btn btn-ghost btn-icon" onClick={() => navigate('/candidates')} aria-label="Back"><ArrowLeft size={16} /></button>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <div className="avatar avatar-lg">{(c.name || '?')[0].toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
                <h1 style={{ fontFamily: "'Inter', sans-serif", fontSize: 24, fontWeight: 600, letterSpacing: '-0.5px' }}>{c.name}</h1>
                <Badge label={c.final_decision || 'PENDING'} variant={c.final_decision || 'PENDING'} />
              </div>
              <div style={{ fontSize: 13.5, color: 'var(--text3)' }}>{c.job_title || 'Candidate Profile'}</div>
            </div>
            
            {/* Score */}
            <div style={{ textAlign: 'right', background: 'var(--surface2)', padding: '10px 16px', borderRadius: 12, border: '1px solid var(--border)' }}>
              <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 28, fontWeight: 700, lineHeight: 1, color: c.match_score >= 75 ? 'var(--green)' : c.match_score >= 50 ? 'var(--amber)' : 'var(--red)' }}>
                {c.match_score ?? '—'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text4)', fontFamily: "'DM Mono', monospace", marginTop: 4, letterSpacing: 1 }}>MATCH SCORE</div>
            </div>
          </div>
          
          <div className="meta-row" style={{ marginTop: 16 }}>
            {c.email      && <span className="meta-item"><Mail size={13} /> {c.email}</span>}
            {c.github_handle && <span className="meta-item"><GitBranch size={13} /> <a href={`https://github.com/${c.github_handle}`} target="_blank" rel="noreferrer">@{c.github_handle}</a></span>}
            {c.university && <span className="meta-item"><GraduationCap size={13} /> {c.university}{c.cgpa ? ` · GPA ${c.cgpa}` : ''}</span>}
            {c.years_of_experience != null && <span className="meta-item"><Calendar size={13} /> {c.years_of_experience} yrs exp</span>}
          </div>
        </div>
      </div>

      {/* Action Bar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 24, padding: 12, background: 'var(--surface)', borderRadius: 12, border: '1px solid var(--border)' }}>
        {!c.email_sent && c.email && (
          <button className="btn btn-gold" onClick={handleSendEmail} disabled={sending}>
            {sending ? <div className="spinner" style={{ borderWidth: 2 }} /> : <Send size={14} />} 
            {sending ? 'Sending…' : 'Send Outreach'}
          </button>
        )}
        {c.email_sent && <span className="badge badge-green" style={{ padding: '6px 14px' }}>✓ Outreach Sent</span>}
        
        <button className="btn btn-blue" onClick={() => setShowAssess(true)}>
          <Calendar size={14} /> Create Assessment
        </button>
        
        <button className="btn btn-ghost" style={{ color: 'var(--red)', marginLeft: 'auto' }} onClick={() => setConfirm({ open: true })}>
          <Trash2 size={14} /> Delete Profile
        </button>
      </div>

      {/* Tabs */}
      <div className="tabs tabs-pill" style={{ marginBottom: 20 }}>
        {['overview', 'analysis', 'email', 'github'].map(t => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'overview' && (
        <div className="grid-2">
          <div className="col-r">
            {/* Skills */}
            <div className="card">
              <div className="card-hdr"><span className="card-title">Skill Profile</span></div>
              <div className="card-body">
                <div className="section-title">Matched Skills</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 20 }}>
                  {(c.skill_matches || []).map((s, i) => <span key={i} className="skill-tag matched">{typeof s === 'string' ? s : s.skill_name}</span>)}
                  {!c.skill_matches?.length && <span style={{ color: 'var(--text4)', fontSize: 13 }}>None detected</span>}
                </div>
                
                <div className="section-title">Languages</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {(c.language_matches || []).map((s, i) => <span key={i} className="skill-tag matched">{typeof s === 'string' ? s : s.language}</span>)}
                  {!c.language_matches?.length && <span style={{ color: 'var(--text4)', fontSize: 13 }}>None detected</span>}
                </div>
              </div>
            </div>

            {/* Evaluation Notes */}
            <div className="card">
              <div className="card-hdr"><span className="card-title">Evaluation Summary</span></div>
              <div className="card-body">
                <div className="section-title" style={{ color: 'var(--green)' }}>Strengths</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
                  {(c.strengths || []).map((s, i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, fontSize: 13.5, color: 'var(--text2)', alignItems: 'flex-start', background: 'var(--surface2)', padding: '12px 16px', borderRadius: 10, borderLeft: '3px solid var(--green)', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
                      <span style={{ color: 'var(--green)', flexShrink: 0 }}>✓</span>
                      <span style={{ lineHeight: 1.5 }}>{s}</span>
                    </div>
                  ))}
                  {!c.strengths?.length && <div style={{ color: 'var(--text4)', fontSize: 13.5, padding: '12px 16px', background: 'var(--surface2)', borderRadius: 10, border: '1px solid var(--border)' }}>No strengths noted</div>}
                </div>
                
                <div className="section-title" style={{ color: 'var(--red)' }}>Red Flags</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
                  {(c.red_flags || []).map((s, i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, fontSize: 13.5, color: 'var(--red)', alignItems: 'flex-start', background: 'var(--red-bg)', padding: '12px 16px', borderRadius: 10, borderLeft: '3px solid var(--red)' }}>
                      <span style={{ color: 'var(--red)', flexShrink: 0 }}>!</span>
                      <span style={{ lineHeight: 1.5 }}>{s}</span>
                    </div>
                  ))}
                  {!c.red_flags?.length && <div style={{ color: 'var(--text4)', fontSize: 13.5, padding: '12px 16px', background: 'var(--surface2)', borderRadius: 10, border: '1px solid var(--border)' }}>No red flags detected</div>}
                </div>
                
                {c.cultural_fit_notes && (
                  <>
                    <div className="section-title">Cultural Fit & Scoring Breakdown</div>
                    {(() => {
                      const notes = c.cultural_fit_notes;
                      if (notes.includes('-> score') || notes.match(/\d+\.?\d*\/\d+/)) {
                        const parts = notes.split(/,(?=\s*[A-Z][A-Za-z\s&]+:\s*\d)/);
                        return (
                          <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
                            {parts.map((part, i) => {
                              const match = part.trim().match(/^(.*?):\s*([0-9.]+)\/([0-9.]+)\s*\((.*?)\)/);
                              if (match) {
                                const [_, category, score, max, details] = match;
                                const pct = (parseFloat(score) / parseFloat(max)) * 100;
                                const isHigh = pct >= 80;
                                const isMed = pct >= 50;
                                const color = isHigh ? 'var(--green)' : isMed ? 'var(--amber)' : 'var(--red)';
                                return (
                                  <div key={i} style={{ background: 'var(--surface2)', padding: '14px 18px', borderRadius: 12, border: '1px solid var(--border)', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                                      <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>{category}</span>
                                      <span style={{ fontSize: 12, color, fontFamily: "'DM Mono', monospace", fontWeight: 700, background: 'var(--surface)', padding: '4px 10px', borderRadius: 20, border: '1px solid var(--border)' }}>
                                        {score}/{max}
                                      </span>
                                    </div>
                                    <div style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 14, lineHeight: 1.6 }}>{details}</div>
                                    <div style={{ height: 6, background: 'var(--surface)', borderRadius: 3, overflow: 'hidden' }}>
                                      <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 1s ease' }} />
                                    </div>
                                  </div>
                                );
                              }
                              return <div key={i} style={{ fontSize: 13.5, color: 'var(--text2)', background: 'var(--surface2)', padding: '12px 16px', borderRadius: 10, border: '1px solid var(--border)' }}>{part}</div>;
                            })}
                          </div>
                        );
                      }
                      return <p style={{ fontSize: 13.5, color: 'var(--text2)', lineHeight: 1.7, background: 'var(--surface2)', padding: '16px', borderRadius: 10, border: '1px solid var(--border)' }}>{notes}</p>;
                    })()}
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="col-r">
            {/* Score Radar */}
            <div className="card">
              <div className="card-hdr"><span className="card-title">Detailed Scoring</span></div>
              <ScoreRadarChart scores={scores} />
              <div style={{ padding: '0 24px 20px' }}>
                {Object.entries(scores).map(([k, v]) => (
                  <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    <div style={{ width: 130, fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'capitalize' }}>
                      {k.replace(/_/g, ' ')}
                    </div>
                    <ScoreBar score={v} max={10} />
                  </div>
                ))}
              </div>
            </div>

            {/* Projects */}
            <div className="card">
              <div className="card-hdr"><span className="card-title">Project Highlights</span></div>
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '20px' }}>
                {(c.project_highlights || []).map((p, i) => (
                  <div key={i} style={{ 
                    display: 'flex', gap: 14, 
                    padding: '16px', 
                    background: 'var(--surface2)', 
                    border: '1px solid var(--border)', 
                    borderRadius: 10, 
                    borderLeft: '3px solid var(--blue)',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                    alignItems: 'flex-start'
                  }}>
                    <span style={{ color: 'var(--blue)', flexShrink: 0, marginTop: 2 }}>
                      <Code size={16} />
                    </span>
                    <span style={{ fontSize: 13.5, color: 'var(--text2)', lineHeight: 1.6 }}>
                      {typeof p === 'string' ? p : p.description || p.name}
                    </span>
                  </div>
                ))}
                {!c.project_highlights?.length && (
                  <div style={{ color: 'var(--text4)', fontSize: 13.5, padding: '16px', background: 'var(--surface2)', borderRadius: 10, border: '1px solid var(--border)' }}>
                    No projects detailed
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'analysis' && (
        <div className="card">
          <div className="card-hdr"><span className="card-title">AI Deep Analysis</span></div>
          <div className="card-body">
            <div className="grid-2-equal">
              <div style={{ background: 'var(--surface2)', padding: 20, borderRadius: 12 }}>
                <div className="section-title" style={{ color: 'var(--green)' }}>Identified Strengths</div>
                <ul style={{ paddingLeft: 16, color: 'var(--text2)', fontSize: 13.5, lineHeight: 1.6 }}>
                  {(c.strengths || []).map((s, i) => <li key={i} style={{ marginBottom: 8 }}>{s}</li>)}
                  {!c.strengths?.length && <li style={{ color: 'var(--text4)' }}>Nothing significant noted.</li>}
                </ul>
              </div>
              <div style={{ background: 'var(--red-bg)', padding: 20, borderRadius: 12, border: '1px solid var(--red-dim)' }}>
                <div className="section-title" style={{ color: 'var(--red)' }}>Risks & Red Flags</div>
                <ul style={{ paddingLeft: 16, color: 'var(--red)', fontSize: 13.5, lineHeight: 1.6 }}>
                  {(c.red_flags || []).map((s, i) => <li key={i} style={{ marginBottom: 8 }}>{s}</li>)}
                  {!c.red_flags?.length && <li style={{ color: 'var(--text4)' }}>No red flags detected.</li>}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === 'email' && (
        <div className="grid-2-equal">
          {c.outreach_email_draft ? (
            <div className="card">
              <div className="card-hdr">
                <span className="card-title"><span className="dot" style={{ background: 'var(--green)' }} /> Outreach Draft</span>
              </div>
              <div className="card-body">
                <div className="log-box" style={{ background: 'var(--surface2)', color: 'var(--text)', fontSize: 13 }}>
                  {c.outreach_email_draft}
                </div>
              </div>
            </div>
          ) : <div className="empty-state"><div className="empty-state-title">No outreach draft</div></div>}
          
          {c.rejection_email_draft ? (
            <div className="card">
              <div className="card-hdr">
                <span className="card-title"><span className="dot" style={{ background: 'var(--red)' }} /> Rejection Draft</span>
              </div>
              <div className="card-body">
                <div className="log-box" style={{ background: 'var(--surface2)', color: 'var(--text)', fontSize: 13 }}>
                  {c.rejection_email_draft}
                </div>
              </div>
            </div>
          ) : <div className="empty-state"><div className="empty-state-title">No rejection draft</div></div>}
        </div>
      )}

      {tab === 'github' && (
        <div className="card">
          <div className="card-hdr">
            <span className="card-title"><GitBranch size={16} /> GitHub Analysis</span>
            {c.github_handle && (
              <a href={`https://github.com/${c.github_handle}`} target="_blank" rel="noreferrer" className="btn btn-surface btn-sm">
                View Profile ↗
              </a>
            )}
          </div>
          <div className="card-body">
            {c.github_summary ? (
              (() => {
                const parts = c.github_summary.split('REPO DETAILS:');
                const overviewText = parts[0] ? parts[0].trim() : '';
                const reposText = parts[1] ? parts[1].trim() : '';

                const repos = reposText.split('REPO: ').filter(r => r.trim()).map(repoStr => {
                  const fields = repoStr.split(' | ');
                  const name = fields[0]?.trim();
                  const lang = fields.find(f => f.startsWith('LANG:'))?.replace('LANG:', '').trim() || 'N/A';
                  const stars = fields.find(f => f.startsWith('STARS:'))?.replace('STARS:', '').trim() || '0';
                  const topics = fields.find(f => f.startsWith('TOPICS:'))?.replace('TOPICS:', '').trim() || 'none';
                  const relevance = fields.find(f => f.startsWith('RELEVANCE:'))?.replace('RELEVANCE:', '').trim() || 'unrelated';
                  const desc = fields.find(f => f.startsWith('DESC:'))?.replace('DESC:', '').trim() || 'N/A';
                  return { name, lang, stars, topics, relevance, desc };
                });

                return (
                  <div className="col-r" style={{ gap: 24 }}>
                    {(() => {
                      if (!overviewText) return null;
                      
                      const safeMatch = (regex) => { const m = overviewText.match(regex); return m ? m[1].trim() : ''; };
                      const username = safeMatch(/Username:\s*(\S+)/);
                      const repos = safeMatch(/Public Repos:\s*(\d+)/);
                      const followers = safeMatch(/Followers:\s*(\d+)/);
                      const stars = safeMatch(/Total Stars:\s*(\d+)/);
                      const forks = safeMatch(/Total Forks:\s*(\d+)/);
                      
                      const languagesStr = safeMatch(/Top Languages:\s*(.*?)(?=\s*Activity Score:|$)/);
                      const languages = languagesStr ? languagesStr.split(',').map(l => l.trim()) : [];
                      
                      const activityScore = safeMatch(/Activity Score:\s*(.*?)(?=\s*Relevance Score:|$)/);
                      const relevanceScore = safeMatch(/Relevance Score:\s*(.*?)(?=\s*Highly Relevant Repos|\s*Somewhat Relevant Repos|\s*Skill Evidence|$)/);
                      
                      const skillEvidenceStr = safeMatch(/Skill Evidence:\s*(\{.*\})/);
                      let skillEvidence = null;
                      if (skillEvidenceStr) {
                        try { skillEvidence = JSON.parse(skillEvidenceStr); } catch(e) {}
                      }

                      if (!repos && !stars) {
                        // Fallback if parsing fails
                        return <div style={{ fontSize: 14, color: 'var(--text2)', lineHeight: 1.7, background: 'var(--surface2)', padding: 20, borderRadius: 12 }}>{overviewText}</div>;
                      }

                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                          {/* Top KPIs */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
                            {[
                              { label: 'Public Repos', val: repos },
                              { label: 'Total Stars', val: stars },
                              { label: 'Followers', val: followers },
                              { label: 'Total Forks', val: forks },
                            ].map((kpi, i) => (
                              <div key={i} style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12, padding: '20px 16px', textAlign: 'center', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
                                <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text)', fontFamily: "'DM Mono', monospace", marginBottom: 6 }}>{kpi.val || '0'}</div>
                                <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1.5 }}>{kpi.label}</div>
                              </div>
                            ))}
                          </div>
                          
                          {/* Scores Row */}
                          <div className="grid-2-equal" style={{ gap: 12 }}>
                            {activityScore && (
                              <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12, padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                                <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 8 }}>Activity Score</div>
                                <div style={{ fontSize: 15, color: 'var(--blue)', fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>{activityScore}</div>
                              </div>
                            )}
                            {relevanceScore && (
                              <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12, padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                                <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 8 }}>Relevance Score</div>
                                <div style={{ fontSize: 15, color: 'var(--gold)', fontWeight: 600, fontFamily: "'Inter', sans-serif" }}>{relevanceScore}</div>
                              </div>
                            )}
                          </div>

                          {/* Languages & Skills */}
                          <div className="grid-2-equal" style={{ gap: 12 }}>
                            {languages.length > 0 && (
                              <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12, padding: '20px' }}>
                                <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 16 }}>Top Languages</div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                  {languages.map(l => <span key={l} className="badge" style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)', padding: '6px 12px' }}>{l}</span>)}
                                </div>
                              </div>
                            )}
                            {skillEvidence && (
                              <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 12, padding: '20px' }}>
                                <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 16 }}>Detected Tech Stack</div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                  {Object.keys(skillEvidence).map(skill => (
                                    <span key={skill} className="badge badge-match" style={{ padding: '6px 12px' }}>{skill}</span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                    
                    {repos.length > 0 && (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 16 }}>
                        {repos.map((r, i) => (
                          <div key={i} style={{ background: 'var(--surface2)', padding: '24px', border: '1px solid var(--border)', borderRadius: '16px', display: 'flex', flexDirection: 'column', transition: 'transform 0.2s, box-shadow 0.2s' }}
                               onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 24px rgba(0,0,0,0.12)'; e.currentTarget.style.borderColor = 'var(--border2)'; }}
                               onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                          >
                            <div style={{ fontWeight: 600, fontSize: 16, color: 'var(--text)', marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, lineHeight: 1.4 }}>
                              <span style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                                <GitBranch size={18} style={{ color: 'var(--text3)', marginTop: 2, flexShrink: 0 }} />
                                <span style={{ wordBreak: 'break-word', fontFamily: "'Inter', sans-serif" }}>{r.name}</span>
                              </span>
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--gold)', display: 'flex', alignItems: 'center', gap: 4, background: 'var(--gold-bg)', border: '1px solid var(--gold-dim)', padding: '4px 10px', borderRadius: 20 }}>
                                ★ {r.stars}
                              </span>
                            </div>
                            
                            <div style={{ fontSize: 13.5, color: 'var(--text2)', marginBottom: 20, lineHeight: 1.6, flex: 1 }}>
                              {r.desc !== 'N/A' && r.desc !== 'None' ? r.desc : <span style={{ fontStyle: 'italic', color: 'var(--text4)' }}>No description provided</span>}
                            </div>
                            
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 'auto', paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                               {r.relevance === 'highly_relevant' && <span className="badge badge-match" style={{ padding: '6px 12px' }}>Highly Relevant</span>}
                               {r.relevance === 'somewhat_relevant' && <span className="badge badge-maybe" style={{ padding: '6px 12px' }}>Somewhat Relevant</span>}
                               {r.lang && r.lang !== 'N/A' && <span className="badge" style={{ background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text3)', padding: '6px 12px' }}>{r.lang}</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()
            ) : (
              <div className="empty-state"><div className="empty-state-icon"><GitBranch size={24}/></div><div className="empty-state-title">No GitHub data available</div></div>
            )}
          </div>
        </div>
      )}

      {/* Create Assessment Modal */}
      {showAssess && (
        <Modal
          title="Issue Assessment"
          onClose={() => { setShowAssess(false); setAssessResult(null); }}
          footer={!assessResult && (
            <>
              <button className="btn btn-ghost" onClick={() => setShowAssess(false)}>Cancel</button>
              <button className="btn btn-gold" onClick={handleCreateAssessment} disabled={creating || !assessJobId}>
                {creating ? <><div className="spinner" style={{ borderWidth: 2 }} /> Generating AI Assessment…</> : 'Generate Assessment'}
              </button>
            </>
          )}
        >
          {assessResult ? (
            <div style={{ textAlign: 'center', padding: '32px 16px' }}>
              <div style={{ fontSize: 40, marginBottom: 16 }}>🎉</div>
              <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8, color: 'var(--text)' }}>Assessment Ready</div>
              <div style={{ fontSize: 13.5, color: 'var(--text3)', marginBottom: 24 }}>Share this unique secure link with the candidate:</div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px' }}>
                <Link size={16} style={{ color: 'var(--text4)', flexShrink: 0 }} />
                <div style={{ fontFamily: "'DM Mono', monospace", fontSize: 13, color: 'var(--blue)', flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {assessResult.url}
                </div>
              </div>
              
              <button 
                className="btn btn-gold btn-lg" 
                style={{ marginTop: 24, width: '100%', justifyContent: 'center' }} 
                onClick={() => {
                  navigator.clipboard.writeText(assessResult.url);
                  toast.success('Link copied to clipboard!');
                }}
              >
                Copy Link to Clipboard
              </button>
            </div>
          ) : (
            <>
              <div className="form-group">
                <label className="form-label">Target Role (Job Posting)</label>
                <select className="form-select" value={assessJobId} onChange={e => setAssessJobId(e.target.value)}>
                  {jobs.map(j => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}
                </select>
                <div className="form-hint" style={{ marginTop: 12 }}>
                  The AI will dynamically generate coding questions, MCQs, and scenarios tailored to the requirements of this specific job and the candidate's resume gaps.
                </div>
              </div>
            </>
          )}
        </Modal>
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={confirm.open}
        title="Delete Candidate Profile"
        message={`Are you sure you want to permanently delete ${c.name}? All evaluation data will be lost.`}
        confirmLabel="Delete Profile"
        onConfirm={handleDelete}
        onCancel={() => setConfirm({ open: false })}
      />
    </>
  );
}
