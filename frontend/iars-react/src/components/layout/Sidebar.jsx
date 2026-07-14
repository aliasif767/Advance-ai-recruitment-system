import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Briefcase, Users,
  ClipboardList, Zap, X
} from 'lucide-react';

const NAV = [
  {
    label: 'Overview',
    items: [
      { to: '/',           icon: LayoutDashboard, label: 'Dashboard' },
    ],
  },
  {
    label: 'Recruitment',
    items: [
      { to: '/jobs',       icon: Briefcase,       label: 'Jobs' },
      { to: '/candidates', icon: Users,           label: 'Candidates' },
      { to: '/pipeline',   icon: Zap,             label: 'Pipeline' },
    ],
  },
  {
    label: 'Assessments',
    items: [
      { to: '/assessments', icon: ClipboardList,  label: 'Assessments' },
    ],
  },
];

export default function Sidebar({ isOpen, onClose }) {
  return (
    <aside className={`sidebar${isOpen ? ' open' : ''}`} aria-label="Main navigation">
      {/* Logo */}
      <div className="logo">
        <div className="logo-wrap">
          <div className="logo-icon">AI</div>
          <div>
            <div className="logo-mark">IARS</div>
            <div className="logo-sub">Recruitment OS</div>
          </div>
          {/* Mobile close button */}
          <button
            className="btn btn-ghost btn-icon btn-sm"
            onClick={onClose}
            aria-label="Close sidebar"
            style={{ marginLeft: 'auto', display: 'none' }}
            id="sidebar-close-btn"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="nav" role="navigation">
        {NAV.map(sec => (
          <div className="nav-sec" key={sec.label}>
            <div className="nav-lbl" aria-hidden="true">{sec.label}</div>
            {sec.items.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
                aria-current={({ isActive }) => isActive ? 'page' : undefined}
                onClick={onClose}
              >
                <item.icon className="nav-icon" size={16} aria-hidden="true" />
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* Footer user area */}
      <div className="sb-footer">
        <div className="sb-user" tabIndex={0} role="button" aria-label="User menu">
          <div className="avatar">HR</div>
          <div className="sb-user-info">
            <div className="sb-user-name">Recruiter</div>
            <div className="sb-user-role">Administrator</div>
          </div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          #sidebar-close-btn { display: flex !important; }
        }
      `}</style>
    </aside>
  );
}
