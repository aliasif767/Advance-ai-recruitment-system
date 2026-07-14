/**
 * ScoreBar — horizontal progress bar with a numeric label.
 * score: 0–max (default max=100)
 */
export default function ScoreBar({ score, max = 100, color }) {
  const pct  = score != null ? Math.min((score / max) * 100, 100) : 0;
  const auto = score == null ? 'var(--border2)'
             : score / max >= 0.7 ? 'var(--green)'
             : score / max >= 0.5 ? 'var(--amber)'
             : 'var(--red)';
  const fill = color || auto;

  return (
    <div className="sb-wrap">
      <div className="sb-bg">
        <div className="sb-fill" style={{ width: `${pct}%`, background: fill }} />
      </div>
      <span className="sb-val" style={{ color: fill }}>
        {score != null ? `${score}${max === 100 ? '' : ''}` : '—'}
      </span>
    </div>
  );
}
