import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  Shield, Camera, Clock, ChevronRight, AlertTriangle,
  Eye, EyeOff, Copy, Maximize, Activity, CheckCircle2,
  BookOpen, Code2, FileText, ToggleLeft, Zap, AlertCircle,
  Lock, Wifi, Monitor
} from 'lucide-react';
import {
  portalInit, startSession, nextQuestion,
  submitAnswer, submitAssessment, logViolation
} from '../api/client';
import Badge from '../components/ui/Badge';

// ── Helpers ──────────────────────────────────────────────────────────
const MCQ_TYPES = ['mcq', 'true false', 'multiple choice'];
const TEXT_TYPES = ['text', 'short answer', 'long answer', 'case study', 'system design', 'fill blank'];
const CODE_TYPES = ['coding', 'sql', 'debugging', 'output prediction'];

function normalizeType(t) {
  if (!t) return '';
  return String(t).toLowerCase().replace(/_/g, ' ').trim();
}

function isCode(q) {
  if (!q || !q.type) return false;
  return CODE_TYPES.includes(normalizeType(q.type));
}

function isText(q) {
  if (!q || !q.type) return false;
  return TEXT_TYPES.includes(normalizeType(q.type));
}

function isMCQ(q) {
  if (!q) return false;
  const type = normalizeType(q.type);
  if (MCQ_TYPES.includes(type)) return true;
  if (q.options && q.options.length > 0 && !isText(q) && !isCode(q)) return true;
  return false;
}

function questionTypeIcon(type) {
  if (MCQ_TYPES.includes(type)) return <ToggleLeft size={13} />;
  if (CODE_TYPES.includes(type)) return <Code2 size={13} />;
  if (['case_study', 'system_design'].includes(type)) return <BookOpen size={13} />;
  return <FileText size={13} />;
}

const fullscreenCenter = {
  minHeight: '100vh',
  background: 'var(--bg)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 24,
};

// ── Timer ──────────────────────────────────────────────────────────
function Timer({ seconds, onExpire }) {
  const [remaining, setRemaining] = useState(seconds);
  const intervalRef = useRef(null);

  useEffect(() => {
    setRemaining(seconds);
  }, [seconds]);

  useEffect(() => {
    if (remaining <= 0) { onExpire?.(); return; }
    intervalRef.current = setInterval(() => setRemaining(r => r - 1), 1000);
    return () => clearInterval(intervalRef.current);
  }, [remaining]);

  const m = Math.floor(remaining / 60).toString().padStart(2, '0');
  const s = (remaining % 60).toString().padStart(2, '0');
  const isDanger = remaining < 120;
  const isWarning = remaining < 300;
  const color = isDanger ? 'var(--red)' : isWarning ? 'var(--amber)' : 'var(--green)';
  const bg = isDanger ? 'var(--red-bg)' : isWarning ? 'var(--amber-bg)' : 'var(--green-bg)';
  const borderColor = isDanger ? 'var(--red-dim)' : isWarning ? 'var(--amber-dim)' : 'var(--green-dim)';

  return (
    <div style={{
      background: bg,
      border: `1px solid ${borderColor}`,
      borderRadius: 12,
      padding: '16px 20px',
      textAlign: 'center',
      animation: isDanger ? 'timerPulse 1s ease infinite' : 'none',
    }}>
      <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", letterSpacing: 2, marginBottom: 4, textTransform: 'uppercase' }}>
        Time Remaining
      </div>
      <div style={{
        fontSize: 32, fontWeight: 700, color,
        fontFamily: "'DM Mono', monospace",
        fontVariantNumeric: 'tabular-nums',
        letterSpacing: 1,
      }}>
        {m}:{s}
      </div>
      {isDanger && (
        <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 6, fontFamily: "'DM Mono', monospace", animation: 'fadeIn 0.3s ease', fontWeight: 600 }}>
          ⚡ HURRY UP
        </div>
      )}
    </div>
  );
}

// ── MCQ Option ─────────────────────────────────────────────────────
function Option({ letter, text, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '16px 20px',
        border: `2px solid ${selected ? 'var(--gold)' : 'var(--border2)'}`,
        borderRadius: 12,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 16,
        background: selected ? 'var(--gold-bg)' : 'var(--surface)',
        transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        marginBottom: 12,
        transform: selected ? 'translateX(4px)' : 'translateX(0)',
        boxShadow: selected ? '0 4px 12px rgba(200,169,110,0.1)' : 'none',
      }}
    >
      <div style={{
        width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
        background: selected ? 'var(--gold)' : 'var(--surface3)',
        border: `2px solid ${selected ? 'var(--gold)' : 'var(--border2)'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 12, fontWeight: 700,
        color: selected ? 'var(--bg)' : 'var(--text3)',
        fontFamily: "'DM Mono', monospace",
        transition: 'all 0.2s',
      }}>
        {selected ? '✓' : letter}
      </div>
      <span style={{ fontSize: 15, color: selected ? 'var(--text)' : 'var(--text2)', lineHeight: 1.6, paddingTop: 3 }}>{text}</span>
    </div>
  );
}

// ── Violation Badge ────────────────────────────────────────────────
function ViolationBadge({ count, label, icon: Icon }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8,
      padding: '8px 12px', borderRadius: 8,
      background: count > 0 ? 'var(--red-bg)' : 'var(--surface3)',
      border: `1px solid ${count > 0 ? 'var(--red-dim)' : 'var(--border)'}`,
      transition: 'all 0.3s',
    }}>
      <Icon size={14} style={{ color: count > 0 ? 'var(--red)' : 'var(--text3)' }} />
      <span style={{ fontSize: 11, color: count > 0 ? 'var(--red)' : 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
        {label}: {count}
      </span>
    </div>
  );
}

// ── Auto-save Indicator ────────────────────────────────────────────
function AutoSaveIndicator({ saved }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6,
      fontSize: 11, color: saved ? 'var(--green)' : 'var(--text3)',
      transition: 'all 0.3s',
      fontFamily: "'DM Mono', monospace"
    }}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: saved ? 'var(--green)' : 'var(--text3)',
        animation: saved ? 'none' : 'pulse 1s ease infinite',
      }} />
      {saved ? 'Auto-saved' : 'Saving…'}
    </div>
  );
}

// ── Main Portal ────────────────────────────────────────────────────
export default function AssessmentPortalPage() {
  const { token } = useParams();
  const [phase, setPhase] = useState('loading');
  const [info, setInfo] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const [question, setQuestion] = useState(null);
  const [answer, setAnswer] = useState('');
  const [answered, setAnswered] = useState(0);
  const [total, setTotal] = useState(0);
  const [startTime, setStartTime] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Tracking state
  const [violations, setViolations] = useState({
    tabSwitch: 0,
    copyPaste: 0,
    rightClick: 0,
    fullscreenExit: 0,
  });
  const [procAlerts, setProcAlerts] = useState([]);
  const [autoSaved, setAutoSaved] = useState(true);
  const [questionTimeSpent, setQuestionTimeSpent] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('online');
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);

  const videoRef = useRef(null);
  const textareaRef = useRef(null);
  const questionTimerRef = useRef(null);
  const autoSaveRef = useRef(null);
  const sessionIdRef = useRef(null);
  const infoRef = useRef(null);

  useEffect(() => { sessionIdRef.current = sessionId; }, [sessionId]);
  useEffect(() => { infoRef.current = info; }, [info]);

  const addAlert = useCallback((msg, type = 'error') => {
    const id = Date.now();
    setProcAlerts(prev => [...prev.slice(-2), { id, msg, type }]);
    setTimeout(() => setProcAlerts(prev => prev.filter(a => a.id !== id)), 4000);
  }, []);

  const recordViolation = useCallback((violationType, description) => {
    setViolations(prev => ({
      ...prev,
      [violationType]: (prev[violationType] || 0) + 1,
    }));
    const sid = sessionIdRef.current;
    const inf = infoRef.current;
    if (sid && inf?.assessment_id) {
      logViolation(inf.assessment_id, sid, {
        candidate_id: '',
        violation_type: violationType,
        description,
      }).catch(() => {});
    }
  }, []);

  useEffect(() => {
    portalInit(token)
      .then(data => {
        setInfo(data);
        setTotal(data.total_questions || 0);
        setPhase('lobby');
      })
      .catch(() => setPhase('error'));
  }, [token]);

  useEffect(() => {
    if (phase !== 'assessment') return;
    const handler = () => {
      if (document.hidden) {
        recordViolation('tabSwitch', 'Candidate switched or minimized browser tab');
        addAlert('⚠ Tab switch detected! This has been recorded.', 'error');
      }
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, [phase, recordViolation, addAlert]);

  useEffect(() => {
    if (phase !== 'assessment') return;
    const handleCopy = () => {
      recordViolation('copyPaste', 'Candidate attempted to copy content');
      addAlert('⚠ Copying is not allowed!', 'warning');
    };
    const handlePaste = () => {
      recordViolation('copyPaste', 'Candidate pasted content');
      addAlert('⚠ Paste detected and recorded.', 'warning');
    };
    document.addEventListener('copy', handleCopy);
    document.addEventListener('cut', handleCopy);
    document.addEventListener('paste', handlePaste);
    return () => {
      document.removeEventListener('copy', handleCopy);
      document.removeEventListener('cut', handleCopy);
      document.removeEventListener('paste', handlePaste);
    };
  }, [phase, recordViolation, addAlert]);

  useEffect(() => {
    if (phase !== 'assessment') return;
    const handler = (e) => {
      e.preventDefault();
      recordViolation('rightClick', 'Candidate attempted right-click');
      addAlert('⚠ Right-click is disabled during exam.', 'info');
    };
    document.addEventListener('contextmenu', handler);
    return () => document.removeEventListener('contextmenu', handler);
  }, [phase, recordViolation, addAlert]);

  useEffect(() => {
    if (phase !== 'assessment') return;
    const handler = (e) => {
      if (
        (e.ctrlKey && e.shiftKey && ['I', 'J', 'C', 'U'].includes(e.key.toUpperCase())) ||
        (e.key === 'F12') ||
        (e.ctrlKey && e.key === 'u') ||
        (e.altKey && e.key === 'Tab')
      ) {
        e.preventDefault();
        recordViolation('tabSwitch', `Suspicious keyboard shortcut: ${e.key}`);
        addAlert('⚠ Keyboard shortcut blocked!', 'warning');
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [phase, recordViolation, addAlert]);

  useEffect(() => {
    if (phase !== 'assessment') return;
    const handler = () => {
      const inFullscreen = !!document.fullscreenElement;
      setIsFullscreen(inFullscreen);
      if (!inFullscreen) {
        recordViolation('fullscreenExit', 'Candidate exited fullscreen mode');
        addAlert('⚠ Please stay in fullscreen mode!', 'error');
      }
    };
    document.addEventListener('fullscreenchange', handler);
    return () => document.removeEventListener('fullscreenchange', handler);
  }, [phase, recordViolation, addAlert]);

  useEffect(() => {
    const onOnline = () => setConnectionStatus('online');
    const onOffline = () => {
      setConnectionStatus('offline');
      addAlert('⚠ Internet connection lost!', 'error');
    };
    window.addEventListener('online', onOnline);
    window.addEventListener('offline', onOffline);
    return () => {
      window.removeEventListener('online', onOnline);
      window.removeEventListener('offline', onOffline);
    };
  }, [addAlert]);

  useEffect(() => {
    if (phase !== 'assessment') return;
    clearInterval(questionTimerRef.current);
    setQuestionTimeSpent(0);
    questionTimerRef.current = setInterval(() => {
      setQuestionTimeSpent(t => t + 1);
    }, 1000);
    return () => clearInterval(questionTimerRef.current);
  }, [phase, question?.id]);

  useEffect(() => {
    if (!answer || phase !== 'assessment') return;
    setAutoSaved(false);
    clearTimeout(autoSaveRef.current);
    autoSaveRef.current = setTimeout(() => setAutoSaved(true), 1500);
    return () => clearTimeout(autoSaveRef.current);
  }, [answer, phase]);

  const initCamera = useCallback(async () => {
    if (!info?.camera_enabled) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch { console.warn('Camera not available'); }
  }, [info]);

  const requestFullscreen = async () => {
    try {
      await document.documentElement.requestFullscreen();
      setIsFullscreen(true);
    } catch { console.warn('Fullscreen not available'); }
  };

  const loadNextQuestion = async (aId, sId) => {
    const res = await nextQuestion(aId, sId);
    if (res.complete) {
      try {
        await submitAssessment(aId);
      } catch (e) {
        // Continue to done phase even if it fails, so user isn't stuck
        console.error('Auto-submit failed:', e);
      }
      setPhase('done');
      return;
    }
    setQuestion(res.question);
    setAnswer('');
    setStartTime(Date.now());
    setAutoSaved(true);
  };

  const handleStart = async () => {
    try {
      await requestFullscreen();
      const sess = await startSession(info.assessment_id);
      setSessionId(sess.session_id);
      setTimeRemaining(sess.time_remaining_seconds);
      await initCamera();
      setPhase('assessment');
      setStartTime(Date.now());
      await loadNextQuestion(info.assessment_id, sess.session_id);
    } catch (e) { addAlert('Failed to start: ' + e.message, 'error'); }
  };

  const isAnswerValid = () => {
    if (!question) return false;
    if (isMCQ(question)) return answer !== '' && answer !== null;
    if (isText(question) || isCode(question)) return answer.trim().length > 0;
    return true; 
  };

  const handleNext = async () => {
    if (!isAnswerValid()) return;
    setSubmitting(true);
    try {
      const timeTaken = Math.round((Date.now() - startTime) / 1000);
      await submitAnswer(info.assessment_id, sessionId, {
        question_id: question.id,
        answer,
        time_taken_seconds: timeTaken,
      });
      setAnswered(prev => prev + 1);
      await loadNextQuestion(info.assessment_id, sessionId);
    } catch (e) { addAlert('Error submitting: ' + e.message, 'error'); }
    finally { setSubmitting(false); }
  };

  const handleSubmit = async () => {
    setShowSubmitConfirm(false);
    setSubmitting(true);
    try {
      await submitAssessment(info.assessment_id);
      setPhase('done');
    } catch (e) { addAlert('Failed to submit: ' + e.message, 'error'); }
    finally { setSubmitting(false); }
  };

  const totalViolations = Object.values(violations).reduce((a, b) => a + b, 0);
  const progress = total > 0 ? (answered / total) * 100 : 0;
  const wordCount = typeof answer === 'string' ? answer.trim().split(/\s+/).filter(Boolean).length : 0;

  if (phase === 'loading') {
    return (
      <div style={fullscreenCenter}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ width: 48, height: 48, borderWidth: 4, margin: '0 auto 24px' }} />
          <div style={{ fontFamily: "'Fraunces', serif", fontSize: 24, color: 'var(--gold2)', marginBottom: 8 }}>Loading Assessment</div>
          <div style={{ fontSize: 14, color: 'var(--text3)' }}>Secure connection establishing…</div>
        </div>
      </div>
    );
  }

  if (phase === 'error') {
    return (
      <div style={fullscreenCenter}>
        <div style={{ textAlign: 'center', maxWidth: 400, padding: 40 }}>
          <div style={{ color: 'var(--text4)', marginBottom: 24 }}><Lock size={64} /></div>
          <h1 style={{ fontFamily: "'Inter', sans-serif", fontSize: 24, fontWeight: 600, marginBottom: 16, color: 'var(--text)' }}>
            Link Invalid or Expired
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text2)', lineHeight: 1.7 }}>
            This assessment session is no longer valid. Please contact the recruitment team to request a new link.
          </p>
        </div>
      </div>
    );
  }

  if (phase === 'done') {
    return (
      <div style={fullscreenCenter}>
        <div className="card" style={{ textAlign: 'center', maxWidth: 560, padding: '48px 40px' }}>
          <div style={{ display: 'inline-flex', padding: 20, borderRadius: '50%', background: 'var(--green-bg)', color: 'var(--green)', marginBottom: 24, animation: 'bounceIn 0.6s cubic-bezier(0.34,1.56,0.64,1)' }}>
            <CheckCircle2 size={48} />
          </div>
          <h1 style={{ fontFamily: "'Fraunces', serif", fontSize: 32, fontWeight: 300, marginBottom: 16, color: 'var(--text)' }}>
            Assessment Complete
          </h1>
          <p style={{ fontSize: 15, color: 'var(--text2)', lineHeight: 1.7, marginBottom: 32 }}>
            Thank you, <strong style={{ color: 'var(--gold2)', fontWeight: 500 }}>{info?.candidate_name}</strong>. Your responses have been securely submitted to our platform. Our team will review your results and be in touch soon.
          </p>

          <div className="grid-2-equal" style={{ gap: 16, marginBottom: 32 }}>
            <StatCard label="Questions Answered" value={`${answered}/${total}`} color="var(--gold)" />
            <StatCard label="Session Status" value="Securely Closed" color="var(--green)" />
          </div>
          
          <div style={{ fontSize: 13, color: 'var(--text3)' }}>You may now close this window.</div>
        </div>
      </div>
    );
  }

  if (phase === 'lobby') {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div style={{ position: 'fixed', top: '20%', left: '50%', transform: 'translate(-50%,-50%)', width: 800, height: 800, background: 'radial-gradient(circle, var(--gold-bg) 0%, transparent 60%)', pointerEvents: 'none' }} />

        <div style={{ maxWidth: 640, width: '100%', position: 'relative', zIndex: 1 }}>
          <div style={{ textAlign: 'center', marginBottom: 40 }}>
            <div className="badge badge-match" style={{ fontSize: 12, padding: '6px 16px', borderRadius: 20, marginBottom: 20 }}>
              <Shield size={12} style={{ marginRight: 6 }} /> IARS Secure Portal
            </div>
            <h1 style={{ fontFamily: "'Fraunces', serif", fontSize: 36, fontWeight: 300, marginBottom: 12, color: 'var(--text)', lineHeight: 1.2 }}>
              {info?.job_title}
            </h1>
            <div style={{ fontSize: 15, color: 'var(--text2)' }}>
              Candidate: <strong style={{ color: 'var(--text)', fontWeight: 500 }}>{info?.candidate_name}</strong>
            </div>
          </div>

          <div className="grid-2-equal" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 32 }}>
            {[
              { icon: Clock, label: 'Duration', val: `${info?.duration_minutes} min`, color: 'var(--blue)' },
              { icon: BookOpen, label: 'Questions', val: info?.total_questions, color: 'var(--gold)' },
              { icon: Shield, label: 'Proctored', val: info?.proctoring_enabled ? 'Yes' : 'No', color: info?.proctoring_enabled ? 'var(--red)' : 'var(--green)' },
            ].map(({ icon: Icon, label, val, color }) => (
              <div key={label} className="card card-lift" style={{ padding: '24px 16px', textAlign: 'center', marginBottom: 0 }}>
                <div style={{ width: 44, height: 44, borderRadius: '50%', background: `color-mix(in srgb, ${color} 15%, transparent)`, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                  <Icon size={20} style={{ color }} />
                </div>
                <div style={{ fontSize: 11, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>{label}</div>
                <div style={{ fontWeight: 600, fontSize: 20, color: 'var(--text)' }}>{val}</div>
              </div>
            ))}
          </div>

          <div className="card" style={{ padding: 32, marginBottom: 24 }}>
            <div style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertCircle size={14} /> Exam Rules
            </div>
            <div style={{ display: 'grid', gap: 14 }}>
              {[
                { icon: EyeOff, rule: 'Do not switch tabs or minimize the browser window' },
                { icon: Copy, rule: 'Copying & pasting is monitored and recorded' },
                { icon: Maximize, rule: 'Stay in fullscreen mode throughout the exam' },
                { icon: Clock, rule: 'Once started, the timer cannot be paused' },
                { icon: Lock, rule: 'Right-click and browser shortcuts are disabled' },
                { icon: Camera, rule: 'Camera may be enabled for identity verification' },
              ].map(({ icon: Icon, rule }, i) => (
                <div key={i} style={{ display: 'flex', gap: 14, fontSize: 14, color: 'var(--text2)', alignItems: 'center' }}>
                  <Icon size={16} style={{ color: 'var(--text4)' }} />
                  {rule}
                </div>
              ))}
            </div>
          </div>

          {info?.proctoring_enabled && (
            <div style={{ background: 'var(--amber-bg)', border: '1px solid var(--amber-dim)', borderRadius: 12, padding: '16px 20px', marginBottom: 24, display: 'flex', gap: 12, alignItems: 'center' }}>
              <Eye size={20} style={{ color: 'var(--amber)', flexShrink: 0 }} />
              <div style={{ fontSize: 14, color: 'var(--amber)', lineHeight: 1.5 }}>
                This is a <strong>proctored</strong> exam. All activity including tab switches, copy/paste, and screen visibility will be monitored and securely recorded.
              </div>
            </div>
          )}

          <button
            className="btn btn-gold btn-lg"
            style={{ width: '100%', justifyContent: 'center', fontSize: 16, borderRadius: 14, padding: '18px' }}
            onClick={handleStart}
          >
            <Zap size={18} /> Begin Assessment
          </button>
          <div style={{ textAlign: 'center', marginTop: 16, fontSize: 12.5, color: 'var(--text3)' }}>
            By starting, you agree to the exam rules and monitoring terms.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', userSelect: 'none' }}
      onCopy={e => e.preventDefault()}
      onCut={e => e.preventDefault()}
    >
      <div style={{ position: 'fixed', top: 24, right: 24, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 360 }}>
        {procAlerts.map(alert => (
          <div key={alert.id} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '14px 18px', borderRadius: 12, fontWeight: 500, fontSize: 13.5,
            background: alert.type === 'error' ? 'var(--red)' : alert.type === 'warning' ? 'var(--amber)' : 'var(--blue)',
            color: 'var(--bg)',
            boxShadow: 'var(--shadow-lg)',
            animation: 'slideIn 0.3s cubic-bezier(0.34,1.56,0.64,1)',
          }}>
            <AlertTriangle size={18} style={{ flexShrink: 0 }} /> {alert.msg}
          </div>
        ))}
      </div>

      {showSubmitConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(8px)' }}>
          <div className="card" style={{ padding: 40, maxWidth: 440, width: '90%', animation: 'fadeUp 0.2s ease', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
              <div style={{ padding: 16, background: 'var(--amber-bg)', color: 'var(--amber)', borderRadius: '50%' }}>
                <AlertTriangle size={32} />
              </div>
            </div>
            <h2 style={{ fontFamily: "'Fraunces', serif", fontWeight: 300, fontSize: 24, textAlign: 'center', marginBottom: 16 }}>Submit Assessment?</h2>
            <p style={{ fontSize: 14.5, color: 'var(--text2)', textAlign: 'center', lineHeight: 1.7, marginBottom: 32 }}>
              You have answered <strong style={{ color: 'var(--gold2)' }}>{answered} out of {total}</strong> questions. This action is final and cannot be undone.
            </p>
            <div className="grid-2-equal" style={{ gap: 12 }}>
              <button className="btn btn-ghost" style={{ justifyContent: 'center' }} onClick={() => setShowSubmitConfirm(false)}>
                Continue Exam
              </button>
              <button className="btn btn-gold" style={{ justifyContent: 'center' }} onClick={handleSubmit} disabled={submitting}>
                {submitting ? 'Submitting…' : 'Submit Now'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div style={{
        background: 'rgba(10, 10, 12, 0.8)', borderBottom: '1px solid var(--border)',
        padding: '12px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        position: 'sticky', top: 0, zIndex: 100, backdropFilter: 'blur(16px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <div style={{ fontFamily: "'Fraunces', serif", fontSize: 16, color: 'var(--gold2)' }}>IARS Portal</div>
          <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
          <div style={{ fontSize: 13, color: 'var(--text3)' }}>{info?.candidate_name}</div>
          <div style={{ width: 1, height: 16, background: 'var(--border)' }} />
          <AutoSaveIndicator saved={autoSaved} />
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="badge" style={{ display: 'flex', gap: 6, background: isFullscreen ? 'var(--green-bg)' : 'var(--red-bg)', borderColor: isFullscreen ? 'var(--green-dim)' : 'var(--red-dim)', color: isFullscreen ? 'var(--green)' : 'var(--red)', cursor: isFullscreen ? 'default' : 'pointer' }}
            onClick={!isFullscreen ? requestFullscreen : undefined}
          >
            <Monitor size={12} />
            {isFullscreen ? 'FULLSCREEN' : 'CLICK TO FULLSCREEN'}
          </div>
          
          <div className="badge" style={{ display: 'flex', gap: 6, background: connectionStatus === 'online' ? 'var(--green-bg)' : 'var(--red-bg)', borderColor: connectionStatus === 'online' ? 'var(--green-dim)' : 'var(--red-dim)', color: connectionStatus === 'online' ? 'var(--green)' : 'var(--red)' }}>
            <Wifi size={12} />
            {connectionStatus.toUpperCase()}
          </div>
          
          {totalViolations > 0 && (
            <div className="badge badge-reject" style={{ display: 'flex', gap: 6, animation: 'fadeIn 0.3s' }}>
              <AlertTriangle size={12} />
              {totalViolations} VIOLATION{totalViolations > 1 ? 'S' : ''}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1 }}>
        <div style={{ width: 300, background: 'var(--surface)', borderRight: '1px solid var(--border)', padding: 24, display: 'flex', flexDirection: 'column', position: 'sticky', top: 57, height: 'calc(100vh - 57px)', overflowY: 'auto' }}>
          
          <Timer seconds={timeRemaining} onExpire={() => handleSubmit()} />

          <div style={{ margin: '24px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text3)', marginBottom: 8, fontFamily: "'DM Mono', monospace", letterSpacing: 1 }}>
              <span>PROGRESS</span>
              <span style={{ color: 'var(--gold2)' }}>{answered}/{total}</span>
            </div>
            <div style={{ height: 6, background: 'var(--surface3)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${progress}%`, background: 'linear-gradient(90deg, var(--gold-dim), var(--gold))', borderRadius: 4, transition: 'width 0.5s ease' }} />
            </div>
          </div>

          <div style={{ background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', marginBottom: 24 }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 6 }}>Time on Question</div>
            <div style={{ fontSize: 24, fontWeight: 700, fontFamily: "'DM Mono', monospace", color: questionTimeSpent > 120 ? 'var(--amber)' : 'var(--text)' }}>
              {Math.floor(questionTimeSpent / 60).toString().padStart(2, '0')}:{(questionTimeSpent % 60).toString().padStart(2, '0')}
            </div>
          </div>

          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", letterSpacing: 1.5, textTransform: 'uppercase', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
              <Activity size={12} /> Proctoring Status
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              <ViolationBadge count={violations.tabSwitch} label="Tab Switches" icon={EyeOff} />
              <ViolationBadge count={violations.copyPaste} label="Copy/Paste" icon={Copy} />
              <ViolationBadge count={violations.fullscreenExit} label="Fullscreen Exit" icon={Maximize} />
              <ViolationBadge count={violations.rightClick} label="Right-Click" icon={Lock} />
            </div>
          </div>

          <div style={{ flex: 1 }} />

          {info?.camera_enabled && (
            <div style={{ borderRadius: 12, overflow: 'hidden', background: '#000', marginBottom: 16, position: 'relative', border: '1px solid var(--border)' }}>
              <video ref={videoRef} autoPlay muted playsInline
                style={{ width: '100%', height: 160, objectFit: 'cover', transform: 'scaleX(-1)', display: 'block' }} />
              <div style={{ position: 'absolute', top: 0, inset: 0, background: 'linear-gradient(to bottom, rgba(0,0,0,0.4) 0%, transparent 40%)' }} />
              <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(0,0,0,0.6)', padding: '4px 10px', borderRadius: 6, backdropFilter: 'blur(4px)' }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--red)', animation: 'pulse 1s ease infinite' }} />
                <span style={{ fontSize: 10, color: 'white', fontFamily: "'DM Mono', monospace", letterSpacing: 1 }}>LIVE REC</span>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: 'var(--text3)' }}>
            <Shield size={12} style={{ color: 'var(--green)' }} /> Session securely monitored
          </div>
        </div>

        <div style={{ flex: 1, padding: '48px 64px', maxWidth: 860, margin: '0 auto', overflowY: 'auto' }}>
          {question ? (
            <>
              <div style={{ marginBottom: 32 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
                  <span className="badge" style={{ background: 'var(--surface2)', color: 'var(--text3)', fontSize: 12 }}>
                    Question {answered + 1} of {total}
                  </span>
                  
                  {question.difficulty && (() => {
                    const diffColors = {
                      hard: 'REJECT',
                      medium: 'MAYBE',
                      easy: 'MATCH'
                    };
                    return <Badge label={question.difficulty.toUpperCase()} variant={diffColors[question.difficulty] || 'PENDING'} />;
                  })()}
                  
                  {question.type && (
                    <span className="badge" style={{ background: 'var(--blue-bg)', border: '1px solid var(--blue-dim)', color: 'var(--blue)' }}>
                      {questionTypeIcon(question.type)}
                      {question.type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                  )}
                  
                  {question.points && (
                    <span style={{ marginLeft: 'auto', fontSize: 14, color: 'var(--gold)', fontFamily: "'DM Mono', monospace", fontWeight: 600 }}>
                      {question.points} pts
                    </span>
                  )}
                </div>

                <div style={{ fontSize: 18, lineHeight: 1.7, color: 'var(--text)', whiteSpace: 'pre-wrap', marginBottom: 12, fontWeight: 400 }}>
                  {question.question_text || question.text}
                </div>

                {question.context && (
                  <div style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', borderRadius: 10, padding: '16px 20px', fontSize: 14, color: 'var(--text2)', lineHeight: 1.7, marginTop: 16, borderLeft: '3px solid var(--gold-dim)' }}>
                    {question.context}
                  </div>
                )}
              </div>

              {isMCQ(question) && (
                <div style={{ marginBottom: 32 }}>
                  {(question.options || []).map((opt, i) => {
                    // Determine the canonical answer value to submit:
                    // - If opt is a string, use it directly
                    // - If opt is an object with an id, use opt.id (matches correct_answers in DB e.g. "a","b")
                    // - Fallback to the letter (A, B, C...)
                    const optId = typeof opt === 'string'
                      ? opt
                      : (opt.id || opt.value || String.fromCharCode(97 + i));
                    const optText = typeof opt === 'string' ? opt : (opt.text || opt.label || String(opt));
                    return (
                      <Option
                        key={i}
                        letter={String.fromCharCode(65 + i)}
                        text={optText}
                        selected={answer === optId}
                        onClick={() => setAnswer(optId)}
                      />
                    );
                  })}
                </div>
              )}

              {isText(question) && (
                <div style={{ marginBottom: 32 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <label style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1 }}>Your Response</label>
                    <div style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
                      {wordCount} words
                    </div>
                  </div>
                  <textarea
                    ref={textareaRef}
                    value={answer}
                    onChange={e => setAnswer(e.target.value)}
                    placeholder="Type your detailed answer here..."
                    style={{
                      width: '100%', background: 'var(--surface)',
                      border: answer.trim().length > 0 ? '2px solid var(--gold-dim)' : '2px solid var(--border)',
                      borderRadius: 12, padding: '16px 20px',
                      color: 'var(--text)', fontFamily: "'Inter', sans-serif", fontSize: 15, lineHeight: 1.7,
                      resize: 'vertical', outline: 'none', transition: 'border-color 0.2s',
                      minHeight: question.type === 'short_answer' ? 100 : 240,
                    }}
                    onFocus={e => { e.target.style.borderColor = 'var(--gold)'; e.target.style.boxShadow = '0 0 0 4px rgba(200,169,110,0.1)'; }}
                    onBlur={e => { e.target.style.borderColor = answer.trim() ? 'var(--gold-dim)' : 'var(--border)'; e.target.style.boxShadow = 'none'; }}
                  />
                </div>
              )}

              {isCode(question) && (
                <div style={{ marginBottom: 32 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <label style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Code2 size={14} /> Integrated IDE
                    </label>
                    <div style={{ fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>{answer.split('\n').length} lines</div>
                  </div>
                  <div style={{ borderRadius: 12, overflow: 'hidden', border: answer.trim().length > 0 ? '2px solid var(--gold-dim)' : '2px solid var(--border)', transition: 'border-color 0.2s' }}>
                    <div style={{ background: '#0D0D0F', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border)' }}>
                      <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FF5F57' }} />
                      <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#FFBD2E' }} />
                      <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#28C840' }} />
                      <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--text3)', fontFamily: "'DM Mono', monospace" }}>
                        {question.type === 'sql' ? 'query.sql' : question.type === 'debugging' ? 'debug.py' : 'solution.py'}
                      </span>
                    </div>
                    <textarea
                      value={answer}
                      onChange={e => setAnswer(e.target.value)}
                      style={{
                        width: '100%', height: 400, background: '#0A0A0C', border: 'none',
                        padding: '16px 20px', color: '#A6E22E', fontFamily: "'DM Mono', monospace",
                        fontSize: 14, lineHeight: 1.7, resize: 'vertical', outline: 'none', display: 'block', tabSize: 2,
                      }}
                      placeholder="# Write your code solution here"
                      onKeyDown={e => {
                        if (e.key === 'Tab') {
                          e.preventDefault();
                          const start = e.target.selectionStart;
                          const end = e.target.selectionEnd;
                          setAnswer(answer.substring(0, start) + '  ' + answer.substring(end));
                          setTimeout(() => { e.target.selectionStart = e.target.selectionEnd = start + 2; }, 0);
                        }
                      }}
                    />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, paddingTop: 24, borderTop: '1px solid var(--border)' }}>
                <button className="btn btn-ghost" style={{ color: 'var(--red)' }} onClick={() => setShowSubmitConfirm(true)} disabled={submitting}>
                  End Assessment
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  {!isAnswerValid() && (
                    <span style={{ fontSize: 13, color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 6 }}>
                      <AlertCircle size={14} /> Answer required to proceed
                    </span>
                  )}
                  <button
                    className="btn btn-gold btn-lg"
                    onClick={handleNext}
                    disabled={submitting || !isAnswerValid()}
                    style={{ minWidth: 140, justifyContent: 'center' }}
                  >
                    {submitting ? 'Saving…' : answered + 1 >= total ? 'Finish Exam' : 'Next Question →'}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 500, gap: 16 }}>
              <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
              <div style={{ color: 'var(--text3)', fontSize: 14 }}>Loading next question…</div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes timerPulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(224,85,85,0.3); }
          50% { box-shadow: 0 0 0 8px rgba(224,85,85,0); }
        }
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(20px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes bounceIn {
          0% { transform: scale(0.5); opacity: 0; }
          70% { transform: scale(1.1); }
          100% { transform: scale(1); opacity: 1; }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className="card" style={{ padding: '20px', textAlign: 'center', marginBottom: 0 }}>
      <div style={{ fontSize: 11, color: 'var(--text3)', fontFamily: "'DM Mono', monospace", textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: color || 'var(--text)', fontFamily: "'DM Mono', monospace" }}>{value}</div>
    </div>
  );
}
