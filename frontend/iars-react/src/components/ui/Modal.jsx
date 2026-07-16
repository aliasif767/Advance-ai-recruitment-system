import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

const WIDTHS = { sm: 420, md: 560, lg: 720, xl: 900 };

export default function Modal({ title, onClose, children, footer, size = 'md' }) {
  const firstFocusRef = useRef(null);

  useEffect(() => {
    const prev = document.activeElement;
    // Focus first interactive element after mount
    setTimeout(() => firstFocusRef.current?.focus(), 50);
    return () => { prev?.focus(); };
  }, []);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') { onClose?.(); return; }
      // Trap focus inside modal
      if (e.key === 'Tab') {
        const modal = firstFocusRef.current?.closest?.('.modal');
        if (!modal) return;
        const focusable = modal.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last  = focusable[focusable.length - 1];
        if (e.shiftKey) { if (document.activeElement === first) { e.preventDefault(); last?.focus(); } }
        else            { if (document.activeElement === last)  { e.preventDefault(); first?.focus(); } }
      }
    };
    window.addEventListener('keydown', handler);
    return () => { window.removeEventListener('keydown', handler); };
  }, [onClose]);

  return (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="modal" style={{ width: WIDTHS[size] || WIDTHS.md }}>
        {/* Header */}
        <div className="modal-hdr">
          <span className="modal-title" id="modal-title">{title}</span>
          <button
            ref={firstFocusRef}
            className="btn btn-ghost btn-icon btn-sm"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">{children}</div>

        {/* Footer */}
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
