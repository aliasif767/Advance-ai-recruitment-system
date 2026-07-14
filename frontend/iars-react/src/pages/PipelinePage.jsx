import { useEffect, useState } from 'react';
import { Play, Loader2, AlertCircle, Trash2, List } from 'lucide-react';
import { listJobs, runPipeline } from '../api/client';
import { useSSE } from '../hooks/useSSE';
import Badge from '../components/ui/Badge';
import { useToast } from '../components/ui/Toast';

export default function PipelinePage() {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [pipelineResult, setPipelineResult] = useState(null);
  
  const events = useSSE(150); // Pipeline logs
  const toast = useToast();

  useEffect(() => {
    listJobs()
      .then((data) => {
        setJobs(data);
        if (data.length > 0) setSelectedJob(data[0].id);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleRunPipeline = async () => {
    if (!selectedJob) return;
    setRunning(true);
    setPipelineResult(null);
    try {
      const result = await runPipeline({ job_id: selectedJob });
      setPipelineResult(result);
      toast.success(`Pipeline executed successfully. Processed ${result.processed_count || 0} candidates.`);
    } catch (e) {
      toast.error('Pipeline failed: ' + e.message);
    } finally {
      setRunning(false);
    }
  };

  const getLogColor = (colorCode) => {
    if (!colorCode) return 'var(--text2)';
    if (colorCode.includes('green') || colorCode === '#3DB87A') return 'var(--green)';
    if (colorCode.includes('red') || colorCode === '#E05555') return 'var(--red)';
    if (colorCode.includes('blue') || colorCode === '#5B9CF6') return 'var(--blue)';
    if (colorCode.includes('amber') || colorCode === '#E8A830' || colorCode === 'yellow') return 'var(--amber)';
    return colorCode; 
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div className="page-header-left">
          <h1>AI Pipeline Engine</h1>
          <p>Manually trigger the recruitment automation workflow</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 360px) 1fr', gap: 20, flex: 1, minHeight: 0 }}>
        
        {/* Left Col: Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-hdr">
              <span className="card-title">Run Pipeline</span>
            </div>
            <div className="card-body">
              <p style={{ fontSize: 13, color: 'var(--text2)', marginBottom: 20, lineHeight: 1.6 }}>
                The AI agent continuously monitors incoming CVs. Trigger manually to instantly process the backlog for a selected job.
              </p>
              
              <div className="form-group">
                <label className="form-label">Target Job Posting</label>
                {loading ? (
                  <div className="skeleton" style={{ height: 38, width: '100%' }} />
                ) : (
                  <select 
                    className="form-select" 
                    value={selectedJob} 
                    onChange={(e) => setSelectedJob(e.target.value)}
                    disabled={running}
                  >
                    <option value="">-- Select a Job --</option>
                    {jobs.map(j => (
                      <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
                    ))}
                  </select>
                )}
              </div>

              <button 
                className="btn btn-gold btn-lg" 
                style={{ width: '100%', marginTop: 8 }}
                onClick={handleRunPipeline}
                disabled={running || !selectedJob || loading}
              >
                {running ? (
                  <><Loader2 size={16} className="spinner" style={{ borderWidth: 0 }} /> Processing…</>
                ) : (
                  <><Play size={16} /> Run AI Pipeline</>
                )}
              </button>

              {pipelineResult && (
                <div style={{ marginTop: 24, padding: 16, border: '1px solid var(--green-dim)', borderRadius: 10, background: 'var(--green-bg)' }}>
                  <div style={{ fontSize: 11, color: 'var(--green)', fontFamily: "'DM Mono', monospace", marginBottom: 10, textTransform: 'uppercase', letterSpacing: 1 }}>
                    Execution Result
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ fontSize: 13, color: 'var(--text)' }}>Status</span>
                    <Badge label={pipelineResult.status || 'Success'} variant="active" />
                  </div>
                  {pipelineResult.processed_count !== undefined && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 13, color: 'var(--text)' }}>CVs Processed</span>
                      <span style={{ fontFamily: "'DM Mono', monospace", fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                        {pipelineResult.processed_count}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Col: Logs */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div className="card-hdr">
            <span className="card-title">
              <span className="pulse" style={{ color: 'var(--green)' }} />
              Live Execution Terminal
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <span style={{ fontSize: 11, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", padding: '4px 8px', background: 'var(--surface2)', borderRadius: 6 }}>SSE Stream</span>
            </div>
          </div>
          
          <div style={{ padding: 16, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
            <div className="log-box" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              {events.length === 0 ? (
                <div className="empty-state" style={{ margin: 'auto' }}>
                  <div className="empty-state-icon"><List size={20} /></div>
                  <div className="empty-state-title">Awaiting activity</div>
                  <div className="empty-state-sub">Logs will stream here when pipeline runs</div>
                </div>
              ) : (
                events.map((ev, i) => (
                  <div key={i} style={{ marginBottom: 6, display: 'flex', gap: 12, borderBottom: '1px solid rgba(255,255,255,0.03)', paddingBottom: 6 }}>
                    <span style={{ color: 'var(--text4)', minWidth: 65, flexShrink: 0 }}>
                      {new Date(ev.timestamp || Date.now()).toLocaleTimeString([], {hour12: false})}
                    </span>
                    <span 
                      style={{ color: getLogColor(ev.color), wordBreak: 'break-word' }}
                      dangerouslySetInnerHTML={{ __html: ev.message || ev.text || '' }}
                    />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
