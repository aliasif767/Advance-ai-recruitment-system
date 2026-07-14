import { Radio } from 'lucide-react';
import { useSSE } from '../../hooks/useSSE';

function timeAgo(ts) {
  if (!ts) return '';
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60)    return `${diff}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function ActivityFeed({ staticEvents = [] }) {
  const liveEvents = useSSE(30);
  const events = liveEvents.length ? liveEvents : staticEvents;

  if (!events.length) {
    return (
      <div className="empty-state" style={{ padding: '40px 20px' }}>
        <div className="empty-state-icon">
          <Radio size={22} />
        </div>
        <div className="empty-state-title">Waiting for activity…</div>
        <div className="empty-state-sub">Events will appear here as the pipeline runs</div>
      </div>
    );
  }

  return (
    <div className="activity-list">
      {events.map((ev, i) => (
        <div className="activity-item" key={i}>
          <div
            className="activity-dot"
            style={{ background: ev.color || 'var(--blue)' }}
          />
          <div className="activity-content">
            <div
              className="activity-text"
              dangerouslySetInnerHTML={{ __html: ev.message || ev.text || '' }}
            />
            <div className="activity-time">{timeAgo(ev.timestamp)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
