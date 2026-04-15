import { useState, useRef, useEffect } from 'react';
import { Settings, LogOut, ChevronDown, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { ThemeSettingsDropdown } from './ThemeSettingsDropdown';

interface HeaderProps {
  title: string;
  logo?:  React.ReactNode;
}

export function Header({ title, logo }: HeaderProps) {
  const { user, logout } = useAuth();

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  /* Close on outside click */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node))
        setSettingsOpen(false);
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node))
        setUserMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <header className="flex-shrink-0 bg-theme-header border-b border-white/20 px-4 h-12 flex items-center gap-3 z-40">

      {/* Logo */}
      {logo && <div className="flex-shrink-0">{logo}</div>}

      {/* Title */}
      <h1 className="text-white font-semibold text-base truncate flex-shrink-0">{title}</h1>

      {/* Spacer */}
      <div className="flex-1" />

      {/* ── Settings menu ── */}
      <div ref={settingsRef} className="relative">
        <button
          onClick={() => { setSettingsOpen(v => !v); setUserMenuOpen(false); }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-white/80 hover:text-white
                     hover:bg-white/10 transition-all text-sm"
          title="הגדרות תצוגה"
        >
          <Settings className="w-4 h-4" />
          <span className="hidden sm:inline text-xs">הגדרות</span>
        </button>

        {settingsOpen && (
          <div className="absolute left-0 top-full mt-1 z-50">
            <ThemeSettingsDropdown />
          </div>
        )}
      </div>

      {/* ── User menu ── */}
      <div ref={userMenuRef} className="relative">
        <button
          onClick={() => { setUserMenuOpen(v => !v); setSettingsOpen(false); }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-white/80 hover:text-white
                     hover:bg-white/10 transition-all"
        >
          <div className="w-7 h-7 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-white" />
          </div>
          <span className="hidden sm:inline text-sm font-medium max-w-[120px] truncate">
            {user?.username ?? 'משתמש'}
          </span>
          <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 hidden sm:block" />
        </button>

        {userMenuOpen && (
          <div className="absolute left-0 top-full mt-1 w-48 bg-white rounded-xl shadow-xl
                          border border-gray-100 z-50 overflow-hidden animate-slide-in">
            <div className="px-4 py-3 border-b border-gray-100">
              <p className="text-sm font-semibold text-gray-800 truncate">{user?.username}</p>
              <p className="text-xs text-gray-400">מנהל מערכת</p>
            </div>
            <button
              onClick={() => { logout(); setUserMenuOpen(false); }}
              className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600
                         hover:bg-red-50 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              התנתקות
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
