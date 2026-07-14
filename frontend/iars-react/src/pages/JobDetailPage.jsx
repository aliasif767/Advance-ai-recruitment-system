import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Globe, ToggleLeft, ToggleRight, Upload, Trash2, MapPin, Clock, DollarSign, Mail, Paperclip } from 'lucide-react';
import { getJob, listCandidates, toggleHiring, postLinkedIn, scoreCVFile, deleteJob } from '../api/client';
import Badge from '../components/ui/Badge';
import ScoreBar from '../components/ui/ScoreBar';
import Modal from '../components/ui/Modal';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { useToast } from '../components/ui/Toast';

export default function JobDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [showUpload, setShowUpload] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  
  const [tab, setTab] = useState('jd');
  const [confirm, setConfirm] = useState({ open: false });
  const toast = useToast();

  const load = async () => {
    setLoading(true);
    try {
      const [j, cands] = await Promise.all([getJob(id), listCandidates({ job_id: id })]);
      setJob(j); 
      setCandidates(cands);
    } catch (e) { 
      toast.error('Failed to load job data'); 
    } finally { 
      setLoading(false); 
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleToggle = async () => {
    try {
      const updated = await toggleHiring(id);
      setJob(updated);
      toast.info(`Hiring ${updated.hiring_active ? 'activated' : 'paused'} for this role`);
    } catch(e) { toast.error('Failed to update status'); }
  };

  const handleLinkedIn = async () => {
    try { 
      await postLinkedIn(id); 
      toast.success('Successfully posted to LinkedIn'); 
      load(); 
    } catch (e) { 
      toast.error('LinkedIn post failed: ' + e.message); 
    }
  };

  const handleDelete = async () => {
    try {
      await deleteJob(id);
      toast.success('Job deleted successfully');
      navigate('/jobs');
    } catch(e) {
      toast.error('Failed to delete job');
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); 
    try {
      const candidate = await scoreCVFile(file, id);
      setCandidates(prev => [candidate, ...prev]);
      setShowUpload(false); 
      setFile(null);
      toast.success('CV scored successfully: ' + candidate.name);
    } catch (e) {
      toast.error('Upload failed: ' + e.message);
    } finally { 
      setUploading(false); 
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); 
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setFile(f);
  };

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;
  if (!job) return <div className="empty-state"><div className="empty-state-title">Job not found</div></div>;

  return (
    <>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 32 }}>
        <div className="page-header-left" style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
          <button className="btn btn-ghost btn-icon" onClick={() => navigate('/jobs')} aria-label="Back"><ArrowLeft size={16} /></button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
              <h1 style={{ fontFamily: "'Inter', sans-serif", fontSize: 24, fontWeight: 600, letterSpacing: '-0.5px', color: 'var(--text)' }}>{job.title}</h1>
              <Badge label={job.status} variant={job.status} />
              {job.hiring_active && <Badge label="Hiring Active" variant="active" dot />}
            </div>
            
            <div style={{ fontSize: 13.5, color: 'var(--text3)' }}>{job.company}</div>
            
            <div className="meta-row" style={{ marginTop: 12 }}>
              {[
                { icon: MapPin, val: job.location },
                { icon: Clock,  val: job.employment_type },
                { icon: DollarSign, val: job.salary_range || 'Competitive' },
                { icon: Mail, val: job.hr_email || '—' },
              ].map(({ icon: Icon, val }) => (
                <span key={val} className="meta-item">
                  <Icon size={12} /> {val}
                </span>
              ))}
            </div>
          </div>
        </div>
        
        <div className="page-header-actions" style={{ flexShrink: 0 }}>
          <button className={`btn ${job.hiring_active ? 'btn-green' : 'btn-ghost'}`} onClick={handleToggle}>
            {job.hiring_active ? <ToggleRight size={14} /> : <ToggleLeft size={14} />}
            {job.hiring_active ? 'Active' : 'Paused'}
          </button>
          
          {!job.linkedin_posted && (
            <button className="btn btn-blue" onClick={handleLinkedIn}>
              <Globe size={14} /> Post to LinkedIn
            </button>
          )}
          
          <button className="btn btn-gold" onClick={() => setShowUpload(true)}>
            <Upload size={14} /> Upload & Score CV
          </button>
          
          <button className="btn btn-ghost btn-icon" style={{ color: 'var(--red)' }} onClick={() => setConfirm({ open: true })}>
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      <div className="grid-2">
        {/* Left: JD / Skills */}
        <div className="card">
          <div className="card-hdr" style={{ padding: '10px 14px' }}>
            <div className="tabs tabs-pill">
              {['jd', 'skills'].map(t => (
                <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
                  {t === 'jd' ? 'Job Description' : 'Required Skills'}
                </button>
              ))}
            </div>
          </div>
          
          {tab === 'jd' && (
            <div className="card-body">
              <div style={{ fontSize: 13.5, color: 'var(--text2)', lineHeight: 1.8, whiteSpace: 'pre-wrap', maxHeight: 600, overflowY: 'auto' }}>
                {job.description || <span style={{ color: 'var(--text4)' }}>No AI description generated yet.</span>}
              </div>
            </div>
          )}
          
          {tab === 'skills' && (
            <div className="card-body">
              <div className="section-title" style={{ marginBottom: 12 }}>Required Skills</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 24 }}>
                {(job.required_skills || []).map(s => <span key={s} className="skill-tag matched">{s}</span>)}
                {!job.required_skills?.length && <span style={{ color: 'var(--text4)', fontSize: 13 }}>None listed</span>}
              </div>
              
              <div className="section-title" style={{ marginBottom: 12 }}>Nice to Have</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {(job.nice_to_have || []).map(s => <span key={s} className="skill-tag">{s}</span>)}
                {!job.nice_to_have?.length && <span style={{ color: 'var(--text4)', fontSize: 13 }}>None listed</span>}
              </div>
            </div>
          )}
        </div>

        {/* Right: Candidates */}
        <div className="card">
          <div className="card-hdr">
            <span className="card-title">
              <span className="dot" style={{ background: 'var(--blue)' }} />
              Applicants ({candidates.length})
            </span>
          </div>
          <div style={{ maxHeight: 660, overflowY: 'auto' }}>
            {!candidates.length && (
              <div className="empty-state" style={{ padding: '60px 32px' }}>
                <div className="empty-state-icon"><Users size={24} /></div>
                <div className="empty-state-title">No candidates yet</div>
                <div className="empty-state-sub">Upload a CV to run the AI scoring engine</div>
                <button className="btn btn-gold btn-sm" style={{ marginTop: 16 }} onClick={() => setShowUpload(true)}>
                  Upload CV
                </button>
              </div>
            )}
            
            {candidates.map(c => (
              <div
                key={c.id}
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', borderBottom: '1px solid var(--border)', cursor: 'pointer', transition: 'background 0.15s' }}
                onClick={() => navigate(`/candidates/${c.id}`)}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <div className="avatar avatar-sm">
                  {(c.name || '?')[0].toUpperCase()}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="candidate-name">{c.name}</div>
                  <div className="candidate-role" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.university || c.email}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                  <Badge label={c.final_decision} variant={c.final_decision} />
                  <div style={{ width: 80 }}><ScoreBar score={c.match_score} /></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {showUpload && (
        <Modal
          title="Upload & Score CV"
          onClose={() => { setShowUpload(false); setFile(null); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowUpload(false)}>Cancel</button>
              <button className="btn btn-gold" onClick={handleUpload} disabled={!file || uploading}>
                {uploading ? <><div className="spinner" style={{ borderWidth: 2 }} /> Scoring…</> : 'Run AI Scoring'}
              </button>
            </>
          }
        >
          <div
            className={`file-drop ${dragOver ? 'drag-over' : ''}`}
            onClick={() => document.getElementById('cv-file-input').click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
          >
            <div className="file-drop-icon"><Paperclip size={20} /></div>
            {file ? (
              <div>
                <div style={{ color: 'var(--gold)', fontWeight: 600, fontSize: 14 }}>{file.name}</div>
                <div style={{ fontSize: 12, marginTop: 6, color: 'var(--text3)' }}>{(file.size / 1024).toFixed(1)} KB · Click to change</div>
              </div>
            ) : (
              <div>
                <div style={{ fontWeight: 500, marginBottom: 6, fontSize: 14, color: 'var(--text2)' }}>Drop CV here or click to browse</div>
                <div style={{ fontSize: 12, color: 'var(--text4)' }}>PDF, DOCX, or TXT</div>
              </div>
            )}
          </div>
          <input id="cv-file-input" type="file" accept=".pdf,.docx,.txt" style={{ display: 'none' }} onChange={e => setFile(e.target.files[0])} />
        </Modal>
      )}

      <ConfirmDialog
        open={confirm.open}
        title="Delete Job"
        message={`Are you sure you want to delete ${job.title}? This removes the job posting but keeps scored candidates.`}
        confirmLabel="Delete Job"
        onConfirm={handleDelete}
        onCancel={() => setConfirm({ open: false })}
      />
    </>
  );
}
