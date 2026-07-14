import { createContext, useContext, useState, useCallback, useRef } from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

const ICONS = {
  success: <CheckCircle size={16} style={{ color: 'var(--green)' }} />,
  error:   <XCircle    size={16} style={{ color: 'var(--red)' }} />,
  warning: <AlertTriangle size={16} style={{ color: 'var(--amber)' }} />,
  info:    <Info       size={16} style={{ color: 'var(--blue)' }} />,
};

const TITLE = {
  success: 'Success',
  error:   'Error',
  warning: 'Warning',
  info:    'Info',
};

let idCounter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.map(t => t.id === id ? { ...t, exiting: true } : t));
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 220);
  }, []);

  const toast = useCallback(({ type = 'info', title, message, duration = 4000 }) => {
    const id = ++idCounter;
    setToasts(prev => [{ id, type, title: title || TITLE[type], message, exiting: false }, ...prev]);
    if (duration > 0) {
      timers.current[id] = setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, [dismiss]);

  const success = useCallback((message, title) => toast({ type: 'success', message, title }), [toast]);
  const error   = useCallback((message, title) => toast({ type: 'error',   message, title }), [toast]);
  const warning = useCallback((message, title) => toast({ type: 'warning', message, title }), [toast]);
  const info    = useCallback((message, title) => toast({ type: 'info',    message, title }), [toast]);

  return (
    <ToastContext.Provider value={{ toast, success, error, warning, info, dismiss }}>
      {children}
      <div className="toast-container" role="region" aria-label="Notifications" aria-live="polite">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`toast toast-${t.type} ${t.exiting ? 'toast-exit' : ''}`}
            role="alert"
          >
            <span className="toast-icon">{ICONS[t.type]}</span>
            <div className="toast-body">
              {t.title && <div className="toast-title" style={{ color: t.type === 'success' ? 'var(--green)' : t.type === 'error' ? 'var(--red)' : t.type === 'warning' ? 'var(--amber)' : 'var(--blue)' }}>{t.title}</div>}
              {t.message && <div className="toast-msg">{t.message}</div>}
            </div>
            <button className="toast-close" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={13} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside ToastProvider');
  return ctx;
}
