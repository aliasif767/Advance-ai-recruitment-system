import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Bell, Settings, Menu, Moon, Sun } from 'lucide-react';

const TITLES = {
  '/':            { title: 'Dashboard',   sub: 'Overview & key metrics' },
  '/jobs':        { title: 'Jobs',        sub: 'Manage job postings' },
  '/candidates':  { title: 'Candidates',  sub: 'Review & score applicants' },
  '/pipeline':    { title: 'AI Pipeline', sub: 'Trigger recruitment automation' },
  '/assessments': { title: 'Assessments', sub: 'Monitor candidate assessments' },
};

export default function Topbar({ onOpenSidebar }) {
  const { pathname } = useLocation();
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  const key = Object.keys(TITLES)
    .filter(k => pathname === k || (k !== '/' && pathname.startsWith(k)))
    .sort((a, b) => b.length - a.length)[0] || '/';

  const { title, sub } = TITLES[key] || TITLES['/'];

  return (
    <header className="topbar">
      <div className="topbar-left">
        {/* Hamburger — visible on mobile only */}
        <button
          className="hamburger"
          onClick={onOpenSidebar}
          aria-label="Open navigation"
          aria-expanded={false}
        >
          <span /><span /><span />
        </button>

        <div>
          <div className="topbar-title">{title}</div>
        </div>
        <span className="topbar-sub">{sub}</span>
      </div>

      <div className="topbar-r">
        <div className="system-status">
          <span className="status-dot" />
          System Active
        </div>

        <button
          className="btn btn-ghost btn-icon"
          onClick={toggleTheme}
          title="Toggle Theme"
          aria-label="Toggle Theme"
        >
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
        </button>

        <button
          className="btn btn-ghost btn-icon"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell size={15} />
        </button>

        <button
          className="btn btn-ghost btn-icon"
          title="Settings"
          aria-label="Settings"
        >
          <Settings size={15} />
        </button>

        <div className="avatar avatar-sm" style={{ cursor: 'pointer' }} title="User menu">
          HR
        </div>
      </div>
    </header>
  );
}
