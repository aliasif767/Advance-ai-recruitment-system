export default function KpiCard({ label, value, sub, accentColor, icon: Icon, trend, dot }) {
  return (
    <div className="kpi">
      <div className="kpi-accent" style={{ background: accentColor || 'var(--gold)' }} />
      <div className="kpi-shine" />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div className="kpi-label">{label}</div>
        {Icon && (
          <div className="kpi-icon">
            <Icon size={20} style={{ color: accentColor || 'var(--gold)' }} />
          </div>
        )}
      </div>

      <div className="kpi-value" style={{ color: accentColor || 'var(--text)' }}>
        {dot && (
          <span style={{
            display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
            background: 'var(--green)', marginRight: 8, marginBottom: 2,
            animation: 'pulse 2s infinite', verticalAlign: 'middle',
          }} />
        )}
        {value ?? '—'}
      </div>

      {sub && (
        <div className="kpi-sub">
          {trend !== undefined && (
            <span className={trend >= 0 ? 'kpi-up' : 'kpi-down'} style={{ marginRight: 4 }}>
              {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
            </span>
          )}
          {sub}
        </div>
      )}
    </div>
  );
}
