import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip
} from 'recharts';

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--surface2)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '8px 12px', fontSize: 12,
      fontFamily: "'DM Mono', monospace"
    }}>
      <div style={{ color: 'var(--text2)' }}>{payload[0]?.payload?.subject}</div>
      <div style={{ color: 'var(--gold2)', fontWeight: 600 }}>{payload[0]?.value}</div>
    </div>
  );
};

export default function ScoreRadarChart({ scores = {} }) {
  const data = Object.entries(scores).map(([key, val]) => ({
    subject: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    value: typeof val === 'number' ? val : 0,
    fullMark: 10,
  }));

  if (!data.length) return null;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="var(--border)" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: 'var(--text3)', fontSize: 10, fontFamily: "'DM Mono', monospace" }}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke="var(--gold)"
          fill="var(--gold)"
          fillOpacity={0.15}
          strokeWidth={2}
        />
        <Tooltip content={<CustomTooltip />} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
