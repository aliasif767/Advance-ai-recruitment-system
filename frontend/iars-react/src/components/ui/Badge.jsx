/**
 * Badge component — maps decision/status strings to styled badges.
 */
const VARIANTS = {
  MATCH:   'badge-match',
  MAYBE:   'badge-maybe',
  REJECT:  'badge-reject',
  PENDING: 'badge-pending',
  active:  'badge-active',
  draft:   'badge-draft',
  closed:  'badge-closed',
  blue:    'badge-blue',
  gold:    'badge-gold',
  purple:  'badge-purple',
  cyan:    'badge-cyan',
};

export default function Badge({ label, variant, dot }) {
  const cls = VARIANTS[variant] || VARIANTS[label] || 'badge-pending';
  return (
    <span className={`badge ${cls}`}>
      {dot && <span className="pulse" style={{ width: 5, height: 5 }} />}
      {label}
    </span>
  );
}
