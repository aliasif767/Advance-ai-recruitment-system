import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Globe, ToggleLeft, ToggleRight, Trash2, MapPin, Clock, Users, Briefcase } from 'lucide-react';
import { listJobs, createJob, deleteJob, toggleHiring, postLinkedIn } from '../api/client';
import Modal         from '../components/ui/Modal';
import Badge         from '../components/ui/Badge';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { useToast }  from '../components/ui/Toast';

const EMPTY_FORM = {
  title: '', company: '', requirements: '', hr_email: '',
  location: 'Remote', employment_type: 'Full-time',
  experience_years: 0, salary_range: '',
  auto_generate_jd: true, auto_post_linkedin: false,
};

export default function JobsPage() {
  const [jobs, setJobs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm]         = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(false);
  const [error, setError]       = useState('');
  const [filter, setFilter]     = useState('all');
  const [confirm, setConfirm]   = useState({ open: false, id: null });
  const navigate = useNavigate();
  const toast    = useToast();

  const load = () => {
    setLoading(true);
    listJobs(filter !== 'all' ? filter : undefined)
      .then(setJobs)
      .catch(console.error)
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [filter]);

  const handleCreate = async () => {
    if (!form.title || !form.company || !form.requirements) {
      setError('Title, company and requirements are required.'); return;
    }
    setCreating(true); setError('');
    try {
      const job = await createJob({ ...form, experience_years: Number(form.experience_years) });
      setJobs(prev => [job, ...prev]);
      setShowModal(false);
      setForm(EMPTY_FORM);
      toast.success('Job posting created successfully.');
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteJob(confirm.id);
      setJobs(prev => prev.filter(j => j.id !== confirm.id));
      toast.success('Job posting deleted.');
    } catch (e) {
      toast.error('Failed to delete job: ' + e.message);
    } finally {
      setConfirm({ open: false, id: null });
    }
  };

  const handleToggle = async (id, e) => {
    e.stopPropagation();
    try {
      const updated = await toggleHiring(id);
      setJobs(prev => prev.map(j => j.id === id ? updated : j));
    } catch (e) {
      toast.error('Failed to update hiring status.');
    }
  };

  const handleLinkedIn = async (id, e) => {
    e.stopPropagation();
    try {
      await postLinkedIn(id);
      toast.success('Successfully posted to LinkedIn!');
      load();
    } catch (err) {
      toast.error('LinkedIn post failed: ' + err.message);
    }
  };

  const f = v => e => setForm(p => ({ ...p, [v]: e.target.value }));
  const fc = v => e => setForm(p => ({ ...p, [v]: e.target.checked }));

  const FILTERS = ['all', 'draft', 'active', 'closed'];

  return (
    <>
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-left">
          <h1>Job Postings</h1>
          <p>{jobs.length} total position{jobs.length !== 1 ? 's' : ''}</p>
        </div>
        <div className="page-header-actions">
          <div className="tabs">
            {FILTERS.map(f => (
              <button
                key={f}
                className={`tab${filter === f ? ' active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <button className="btn btn-gold" onClick={() => setShowModal(true)}>
            <Plus size={14} /> New Job
          </button>
        </div>
      </div>

      {/* Job Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
        {loading && [...Array(3)].map((_, i) => (
          <div key={i} className="card" style={{ padding: 20 }}>
            <div className="skeleton" style={{ height: 16, width: '70%', marginBottom: 10 }} />
            <div className="skeleton" style={{ height: 12, width: '45%', marginBottom: 16 }} />
            <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
              <div className="skeleton" style={{ height: 10, width: 60 }} />
              <div className="skeleton" style={{ height: 10, width: 60 }} />
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <div className="skeleton" style={{ height: 28, width: 60, borderRadius: 7 }} />
              <div className="skeleton" style={{ height: 28, width: 60, borderRadius: 7 }} />
            </div>
          </div>
        ))}

        {!loading && !jobs.length && (
          <div className="empty-state" style={{ gridColumn: '1/-1', padding: '80px 20px' }}>
            <div className="empty-state-icon"><Briefcase size={22} /></div>
            <div className="empty-state-title">No jobs found</div>
            <div className="empty-state-sub">Create your first job posting to get started.</div>
            <div className="empty-state-action">
              <button className="btn btn-gold" onClick={() => setShowModal(true)}>
                <Plus size={14} /> Create Job
              </button>
            </div>
          </div>
        )}

        {jobs.map(job => (
          <div
            key={job.id}
            className="card card-lift"
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/jobs/${job.id}`)}
          >
            <div style={{ padding: '18px 20px' }}>
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div style={{ flex: 1, minWidth: 0, marginRight: 10 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 3, color: 'var(--text)', letterSpacing: '-0.2px' }}>{job.title}</div>
                  <div style={{ fontSize: 12, color: 'var(--text3)' }}>{job.company}</div>
                </div>
                <Badge label={job.status} variant={job.status} />
              </div>

              {/* Meta */}
              <div className="meta-row" style={{ marginBottom: 12, gap: 12 }}>
                <span className="meta-item"><MapPin size={11} /> {job.location}</span>
                <span className="meta-item"><Clock size={11} /> {job.employment_type}</span>
                {job.experience_years > 0 && (
                  <span className="meta-item"><Users size={11} /> {job.experience_years}+ yrs</span>
                )}
              </div>

              {/* Skills */}
              {job.required_skills?.length > 0 && (
                <div style={{ marginBottom: 14, display: 'flex', flexWrap: 'wrap' }}>
                  {job.required_skills.slice(0, 4).map(s => (
                    <span key={s} className="skill-tag">{s}</span>
                  ))}
                  {job.required_skills.length > 4 && (
                    <span className="skill-tag" style={{ color: 'var(--text4)' }}>
                      +{job.required_skills.length - 4}
                    </span>
                  )}
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: 7, borderTop: '1px solid var(--border)', paddingTop: 13 }}>
                <button
                  className={`btn btn-sm ${job.hiring_active ? 'btn-green' : 'btn-ghost'}`}
                  onClick={(e) => handleToggle(job.id, e)}
                  title={job.hiring_active ? 'Disable hiring' : 'Enable hiring'}
                >
                  {job.hiring_active ? <ToggleRight size={13} /> : <ToggleLeft size={13} />}
                  {job.hiring_active ? 'Active' : 'Paused'}
                </button>

                {!job.linkedin_posted && (
                  <button
                    className="btn btn-sm btn-blue"
                    onClick={(e) => handleLinkedIn(job.id, e)}
                  >
                    <Globe size={12} /> LinkedIn
                  </button>
                )}
                {job.linkedin_posted && (
                  <span className="badge badge-blue" style={{ alignSelf: 'center' }}>✓ Posted</span>
                )}

                <button
                  className="btn btn-sm btn-danger"
                  style={{ marginLeft: 'auto' }}
                  onClick={(e) => { e.stopPropagation(); setConfirm({ open: true, id: job.id }); }}
                  aria-label="Delete job"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Create Job Modal */}
      {showModal && (
        <Modal
          title="Create New Job"
          size="lg"
          onClose={() => { setShowModal(false); setError(''); setForm(EMPTY_FORM); }}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowModal(false)}>Cancel</button>
              <button className="btn btn-gold" onClick={handleCreate} disabled={creating}>
                {creating
                  ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Creating…</>
                  : <><Plus size={13} /> Create Job</>}
              </button>
            </>
          }
        >
          {error && (
            <div className="form-error-banner">
              <span>{error}</span>
            </div>
          )}
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Job Title <span className="form-required">*</span></label>
              <input className="form-input" placeholder="e.g. Senior Python Developer" value={form.title} onChange={f('title')} autoFocus />
            </div>
            <div className="form-group">
              <label className="form-label">Company <span className="form-required">*</span></label>
              <input className="form-input" placeholder="e.g. TechCorp Ltd" value={form.company} onChange={f('company')} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Requirements <span className="form-required">*</span></label>
            <textarea className="form-textarea" rows={4} placeholder="Describe key skills, responsibilities, and qualifications…" value={form.requirements} onChange={f('requirements')} />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Location</label>
              <input className="form-input" placeholder="Remote / London / etc." value={form.location} onChange={f('location')} />
            </div>
            <div className="form-group">
              <label className="form-label">Employment Type</label>
              <select className="form-select" value={form.employment_type} onChange={f('employment_type')}>
                <option>Full-time</option>
                <option>Part-time</option>
                <option>Contract</option>
                <option>Internship</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Experience (years)</label>
              <input className="form-input" type="number" min={0} value={form.experience_years} onChange={f('experience_years')} />
            </div>
            <div className="form-group">
              <label className="form-label">Salary Range</label>
              <input className="form-input" placeholder="e.g. £60k–£80k" value={form.salary_range} onChange={f('salary_range')} />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">HR Email</label>
            <input className="form-input" type="email" placeholder="hr@company.com" value={form.hr_email} onChange={f('hr_email')} />
          </div>

          <div style={{ display: 'flex', gap: 20, marginTop: 4 }}>
            <label className="form-check">
              <input type="checkbox" checked={form.auto_generate_jd} onChange={fc('auto_generate_jd')} />
              <span className="form-check-label">Auto-generate JD with AI</span>
            </label>
            <label className="form-check">
              <input type="checkbox" checked={form.auto_post_linkedin} onChange={fc('auto_post_linkedin')} />
              <span className="form-check-label">Post to LinkedIn</span>
            </label>
          </div>
        </Modal>
      )}

      {/* Delete Confirm Dialog */}
      <ConfirmDialog
        open={confirm.open}
        title="Delete Job Posting"
        message="This will permanently delete this job and all related data. This action cannot be undone."
        confirmLabel="Delete Job"
        onConfirm={handleDelete}
        onCancel={() => setConfirm({ open: false, id: null })}
      />
    </>
  );
}
