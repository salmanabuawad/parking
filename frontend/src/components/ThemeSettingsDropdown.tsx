import type { ReactNode } from 'react';
import { Sun, Moon, Contrast, Type } from 'lucide-react';
import { useTheme, type Brightness, type FontSize, type ThemeId } from '../context/ThemeContext';

const brightnessOpts: { value: Brightness; label: string; icon: ReactNode }[] = [
  { value: 'light', label: 'בהיר', icon: <Sun className="w-4 h-4" /> },
  { value: 'normal', label: 'רגיל', icon: <Sun className="w-4 h-4 opacity-60" /> },
  { value: 'dark', label: 'כהה', icon: <Moon className="w-4 h-4" /> },
  { value: 'contrast', label: 'ניגודיות', icon: <Contrast className="w-4 h-4" /> },
];

const fontSizeOpts: { value: FontSize; label: string; size: string }[] = [
  { value: 'small', label: 'קטן', size: 'text-xs' },
  { value: 'normal', label: 'רגיל', size: 'text-sm' },
  { value: 'large', label: 'גדול', size: 'text-base' },
];

const themeOpts: { value: ThemeId; label: string }[] = [
  { value: 'ocean', label: '🌊 Ocean' },
  { value: 'mist', label: '🌫 Mist' },
];

/** Shared panel: theme, brightness, font size (used in Header settings menu and Login). */
export function ThemeSettingsDropdown() {
  const { brightness, setBrightness, themeId, setThemeId, fontSize, setFontSize } = useTheme();

  return (
    <div
      className="w-56 bg-white rounded-xl shadow-xl border border-gray-100 z-50 overflow-hidden animate-slide-in"
      dir="rtl"
    >
      <div className="px-3 pt-3 pb-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">ערכת נושא</p>
        <div className="flex gap-2">
          {themeOpts.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => setThemeId(t.value)}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all
                ${themeId === t.value ? 'bg-theme-accent text-white shadow-sm' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-px bg-gray-100 mx-3" />

      <div className="px-3 py-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">בהירות</p>
        <div className="grid grid-cols-2 gap-1.5">
          {brightnessOpts.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setBrightness(opt.value)}
              className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all
                ${brightness === opt.value ? 'bg-theme-accent text-white shadow-sm' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {opt.icon}
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-px bg-gray-100 mx-3" />

      <div className="px-3 py-2 pb-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 flex items-center gap-1">
          <Type className="w-3 h-3" /> גודל גופן
        </p>
        <div className="flex gap-1.5">
          {fontSizeOpts.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setFontSize(opt.value)}
              className={`flex-1 py-1.5 rounded-lg font-medium transition-all ${opt.size}
                ${fontSize === opt.value ? 'bg-theme-accent text-white shadow-sm' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
