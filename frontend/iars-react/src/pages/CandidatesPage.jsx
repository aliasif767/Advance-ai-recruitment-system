import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, Trash2, Users } from 'lucide-react';
import { listCandidates, listJobs, deleteCandidate } from '../api/client';
import Badge from '../components/ui/Badge';
import ScoreBar from '../components/ui/ScoreBar';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/Toast';

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [decision, setDecision] = useState('all');
  const [jobFilter, setJobFilter] = useState('all');
  const [confirm, setConfirm] = useState({ open: false, id: null });
  const navigate = useNavigate();
  const toast = useToast();

  useEffect(() => {
    listJobs().then(setJobs).catch(console.error);
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = {};
    if (decision !== 'all') params.decision = decision;
    if (jobFilter !== 'all') params.job_id = jobFilter;
    listCandidates(params)
      .then(setCandidates)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [decision, jobFilter]);

  const filtered = candidates.filter(c =>
    !search || c.name?.toLowerCase().includes(search.toLowerCase()) ||
    c.email?.toLowerCase().includes(search.toLowerCase()) ||
    c.job_title?.toLowerCase().includes(search.toLowerCase())
  );

  const handleDelete = async () => {
    try {
      await deleteCandidate(confirm.id);
      setCandidates(candidates.filter(c => c.id !== confirm.id));
      toast.success('Candidate removed successfully');
    } catch (err) {
      toast.error('Failed to delete candidate: ' + err.message);
    } finally {
      setConfirm({ open: false, id: null });
    }
  };

  const getAvatarColor = (name) => {
    const colors = ['var(--blue-bg)', 'var(--purple-bg)', 'var(--amber-bg)', 'var(--green-bg)'];
    const textColors = ['var(--blue)', 'var(--purple)', 'var(--amber)', 'var(--green)'];
    const i = (name?.charCodeAt(0) || 0) % colors.length;
    return { bg: colors[i], color: textColors[i] };
  };

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Candidates</h1>
          <p>{filtered.length} applicant{filtered.length !== 1 ? 's' : ''} in the pipeline</p>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--text3)' }} />
          <input
            className="form-input"
            style={{ paddingLeft: 38 }}
            placeholder="Search by name, email, or role…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        
        <div className="tabs">
          {['all', 'MATCH', 'MAYBE', 'REJECT'].map(d => (
            <button key={d} className={`tab ${decision === d ? 'active' : ''}`} onClick={() => setDecision(d)}>
              {d === 'all' ? 'All Decisions' : d}
            </button>
          ))}
        </div>
        
        <select className="form-select" style={{ width: 220 }} value={jobFilter} onChange={e => setJobFilter(e.target.value)}>
          <option value="all">All Job Postings</option>
          {jobs.map(j => <option key={j.id} value={j.id}>{j.title}</option>)}
        </select>
      </div>

      {/* Table */}
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Job</th>
                <th style={{ width: 140 }}>Match Score</th>
                <th>Decision</th>
                <th>GitHub</th>
                <th>Contact Status</th>
                <th>Applied</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 60 }}>
                  <div className="loading-screen"><div className="spinner" /></div>
                </td></tr>
              )}
              
              {!loading && !filtered.length && (
                <tr><td colSpan={8}>
                  <div className="empty-state">
                    <div className="empty-state-icon"><Users size={24} /></div>
                    <div className="empty-state-title">No candidates found</div>
                    <div className="empty-state-sub">Try adjusting your filters or search query</div>
                  </div>
                </td></tr>
              )}
              
              {filtered.map(c => {
                const avatar = getAvatarColor(c.name);
                return (
                  <tr key={c.id} onClick={() => navigate(`/candidates/${c.id}`)}>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div className="avatar" style={{ width: 32, height: 32, fontSize: 12, background: avatar.bg, color: avatar.color }}>
                          {(c.name || '?')[0].toUpperCase()}
                        </div>
                        <div>
                          <div className="candidate-name">{c.name}</div>
                          <div className="candidate-role">{c.university || c.email}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--text2)' }}>{c.job_title || '—'}</span>
                    </td>
                    <td>
                      <ScoreBar score={c.match_score} />
                    </td>
                    <td>
                      <Badge label={c.final_decision || 'PENDING'} variant={c.final_decision || 'PENDING'} />
                    </td>
                    <td>
                      {c.github_handle ? (
                        <a href={`https://github.com/${c.github_handle}`} target="_blank" rel="noreferrer"
                          onClick={e => e.stopPropagation()}
                          style={{ fontSize: 11.5, color: 'var(--blue)', fontFamily: "'DM Mono', monospace", textDecoration: 'none' }}>
                          @{c.github_handle}
                        </a>
                      ) : <span style={{ color: 'var(--text4)', fontSize: 11.5 }}>—</span>}
                    </td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ fontSize: 11.5, fontWeight: 500, color: c.email_sent ? 'var(--green)' : 'var(--text4)' }}>
                          {c.email_sent ? '✓ Email Sent' : 'Pending'}
                        </span>
                      </span>
                    </td>
                    <td>
                      <span style={{ fontSize: 11.5, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
                        {c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}
                      </span>
                    </td>
                    <td>
                      <button 
                        className="btn btn-ghost btn-sm btn-icon" 
                        style={{ color: 'var(--text3)' }} 
                        onClick={(e) => { e.stopPropagation(); setConfirm({ open: true, id: c.id }); }}
                        title="Delete Candidate"
                        aria-label="Delete"
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <ConfirmDialog
        open={confirm.open}
        title="Delete Candidate"
        message="This will permanently delete the candidate and all their evaluations. This cannot be undone."
        onConfirm={handleDelete}
        onCancel={() => setConfirm({ open: false, id: null })}
        confirmLabel="Delete"
      />
    </>
  );
}
