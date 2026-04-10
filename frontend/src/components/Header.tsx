import { useState, useRef, useEffect } from 'react';
import { Settings, LogOut, Sun, Moon, Contrast, Type, ChevronDown, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme, type Brightness, type FontSize, type ThemeId } from '../context/ThemeContext';

interface HeaderProps {
  title: string;
  logo?:  React.ReactNode;
}

export function Header({ title, logo }: HeaderProps) {
  const { user, logout } = useAuth();
  const { brightness, setBrightness, themeId, setThemeId, fontSize, setFontSize } = useTheme();

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

  const brightnessOpts: { value: Brightness; label: string; icon: React.ReactNode }[] = [
    { value: 'light',    label: 'בהיר',      icon: <Sun className="w-4 h-4" /> },
    { value: 'normal',   label: 'רגיל',      icon: <Sun className="w-4 h-4 opacity-60" /> },
    { value: 'dark',     label: 'כהה',       icon: <Moon className="w-4 h-4" /> },
    { value: 'contrast', label: 'ניגודיות',  icon: <Contrast className="w-4 h-4" /> },
  ];
  const fontSizeOpts: { value: FontSize; label: string; size: string }[] = [
    { value: 'small',  label: 'קטן',  size: 'text-xs' },
    { value: 'normal', label: 'רגיל', size: 'text-sm' },
    { value: 'large',  label: 'גדול', size: 'text-base' },
  ];
  const themeOpts: { value: ThemeId; label: string }[] = [
    { value: 'ocean', label: '🌊 Ocean' },
    { value: 'mist',  label: '🌫 Mist'  },
  ];

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
          <div className="absolute left-0 top-full mt-1 w-56 bg-white rounded-xl shadow-xl
                          border border-gray-100 z-50 overflow-hidden animate-slide-in">

            {/* Theme */}
            <div className="px-3 pt-3 pb-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">ערכת נושא</p>
              <div className="flex gap-2">
                {themeOpts.map(t => (
                  <button
                    key={t.value}
                    onClick={() => setThemeId(t.value)}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all
                      ${themeId === t.value
                        ? 'bg-theme-accent text-white shadow-sm'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-px bg-gray-100 mx-3" />

            {/* Brightness */}
            <div className="px-3 py-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">בהירות</p>
              <div className="grid grid-cols-2 gap-1.5">
                {brightnessOpts.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setBrightness(opt.value)}
                    className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all
                      ${brightness === opt.value
                        ? 'bg-theme-accent text-white shadow-sm'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    {opt.icon}
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="h-px bg-gray-100 mx-3" />

            {/* Font size */}
            <div className="px-3 py-2 pb-3">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                <Type className="w-3 h-3" /> גודל גופן
              </p>
              <div className="flex gap-1.5">
                {fontSizeOpts.map(opt => (
                  <button
                    key={opt.value}
                    onClick={() => setFontSize(opt.value)}
                    className={`flex-1 py-1.5 rounded-lg font-medium transition-all ${opt.size}
                      ${fontSize === opt.value
                        ? 'bg-theme-accent text-white shadow-sm'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
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
