import { useEffect, useRef } from 'react';
import { AlertTriangle, Trash2, X } from 'lucide-react';

/**
 * Premium confirmation dialog — replaces native confirm()
 * 
 * Props:
 *   open     boolean
 *   title    string
 *   message  string
 *   onConfirm  () => void
 *   onCancel   () => void
 *   confirmLabel  string (default "Confirm")
 *   cancelLabel   string (default "Cancel")
 *   variant   'danger' | 'warning' | 'default'
 */
export default function ConfirmDialog({
  open,
  title = 'Are you sure?',
  message,
  onConfirm,
  onCancel,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
}) {
  const confirmRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onCancel?.(); };
    window.addEventListener('keydown', handler);
    // Focus confirm button for keyboard accessibility
    setTimeout(() => confirmRef.current?.focus(), 50);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  if (!open) return null;

  const iconBg    = variant === 'danger'  ? 'var(--red-bg)'   : variant === 'warning' ? 'var(--amber-bg)' : 'var(--surface3)';
  const iconColor = variant === 'danger'  ? 'var(--red)'      : variant === 'warning' ? 'var(--amber)'    : 'var(--text2)';
  const Icon      = variant === 'danger'  ? Trash2            : AlertTriangle;
  const btnClass  = variant === 'danger'  ? 'btn btn-danger'  : variant === 'warning' ? 'btn btn-gold'    : 'btn btn-gold';

  return (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onCancel?.(); }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div className="modal confirm-dialog">
        <div className="modal-hdr">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="confirm-icon" style={{ background: iconBg, border: `1px solid ${iconColor}22`, width: 36, height: 36, marginBottom: 0 }}>
              <Icon size={16} style={{ color: iconColor }} />
            </div>
            <span className="modal-title" id="confirm-title">{title}</span>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onCancel} aria-label="Close">
            <X size={14} />
          </button>
        </div>
        {message && (
          <div className="modal-body" style={{ paddingTop: 16, paddingBottom: 20 }}>
            <p style={{ fontSize: 13.5, color: 'var(--text2)', lineHeight: 1.6 }}>{message}</p>
          </div>
        )}
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel}>{cancelLabel}</button>
          <button ref={confirmRef} className={btnClass} onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
