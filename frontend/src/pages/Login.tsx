import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme, type Brightness } from '../context/ThemeContext'
import { type FontSize } from '../lib/fontSizeStore'
import { Loader2, AlertCircle, Lock, Sun, Moon, Contrast, Type } from 'lucide-react'
import { t } from '../i18n'

export default function Login() {
  const { login }                            = useAuth()
  const { brightness, setBrightness, themeId, setThemeId, fontSize, setFontSize } = useTheme()
  const navigate                             = useNavigate()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPwd,  setShowPwd]  = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState<string | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username.trim(), password)
      navigate('/', { replace: true })
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } } }
      setError(ax.response?.data?.detail || t('loginFailed'))
    } finally {
      setLoading(false)
    }
  }

  const brightnessOptions: { value: Brightness; label: string; icon: JSX.Element }[] = [
    { value: 'light',    label: 'בהיר',     icon: <Sun className="w-4 h-4" /> },
    { value: 'normal',   label: 'רגיל',     icon: <Sun className="w-4 h-4 opacity-60" /> },
    { value: 'dark',     label: 'כהה',      icon: <Moon className="w-4 h-4" /> },
    { value: 'contrast', label: 'ניגודיות', icon: <Contrast className="w-4 h-4" /> },
  ]
  const fontSizeOptions: { value: FontSize; label: string }[] = [
    { value: 'small',  label: 'S' },
    { value: 'normal', label: 'M' },
    { value: 'large',  label: 'L' },
  ]

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-theme-content px-4" dir="rtl">

      {/* ── Top-left accessibility bar ── */}
      <div className="fixed top-3 right-3 flex items-center gap-2 z-50">

        {/* Theme toggle */}
        <button
          onClick={() => setThemeId(themeId === 'ocean' ? 'mist' : 'ocean')}
          title="החלף ערכת נושא"
          className="px-2.5 py-1.5 rounded-md bg-white/80 border border-gray-200 shadow-sm text-xs font-medium
                     text-gray-600 hover:bg-white hover:border-gray-300 transition-all"
        >
          {themeId === 'ocean' ? '🌊 Ocean' : '🌫 Mist'}
        </button>

        {/* Brightness */}
        <div className="flex items-center gap-1 px-1.5 py-1.5 rounded-md bg-white/80 border border-gray-200 shadow-sm">
          {brightnessOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => setBrightness(opt.value)}
              title={opt.label}
              className={`p-1 rounded transition-all ${brightness === opt.value
                ? 'bg-theme-accent text-white shadow-sm'
                : 'text-gray-500 hover:bg-gray-100'}`}
            >
              {opt.icon}
            </button>
          ))}
        </div>

        {/* Font size */}
        <div className="flex items-center gap-1 px-1.5 py-1.5 rounded-md bg-white/80 border border-gray-200 shadow-sm">
          <Type className="w-3.5 h-3.5 text-gray-400 mr-0.5" />
          {fontSizeOptions.map(opt => (
            <button
              key={opt.value}
              onClick={() => setFontSize(opt.value)}
              title={opt.label}
              className={`w-6 h-6 rounded text-xs font-bold transition-all ${fontSize === opt.value
                ? 'bg-theme-accent text-white shadow-sm'
                : 'text-gray-500 hover:bg-gray-100'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Login card ── */}
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-theme-tab-active rounded-2xl shadow-lg mb-4">
            <Lock className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-theme-text-primary mb-1">{t('signInTitle')}</h1>
          <p className="text-theme-text-muted text-sm">{t('signInSubtitle')}</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-8 border border-theme-card-border">
          <form onSubmit={handleSubmit} className="space-y-5">

            {/* Username */}
            <div>
              <label htmlFor="username" className="label-base">{t('username')}</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                disabled={loading}
                autoComplete="username"
                placeholder={t('username')}
                className="input-base disabled:bg-slate-100 disabled:cursor-not-allowed"
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="label-base">{t('password')}</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={loading}
                  autoComplete="current-password"
                  placeholder={t('password')}
                  className="input-base pr-16 disabled:bg-slate-100 disabled:cursor-not-allowed"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd(v => !v)}
                  tabIndex={-1}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-theme-text-muted
                             hover:text-theme-text-primary transition-colors"
                >
                  {showPwd ? 'הסתר' : 'הצג'}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full py-3 px-4 bg-theme-tab-active hover:bg-theme-tab-active-hover text-white
                         font-semibold rounded-lg shadow-md hover:shadow-lg transition-all duration-200
                         disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {loading
                ? <><Loader2 className="w-5 h-5 animate-spin" /><span>{t('signInProgress')}</span></>
                : <span>{t('signIn')}</span>
              }
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-theme-text-muted mt-6">
          © {new Date().getFullYear()} Advanced Parking
        </p>
      </div>
    </div>
  )
}
