import { createContext, useContext, useEffect, useMemo, useState } from 'react'

export type ThemeId  = 'ocean' | 'mist'
export type Brightness = 'normal' | 'dark' | 'contrast' | 'light'
export type FontSize   = 'small' | 'normal' | 'large'

type ThemeState = {
  themeId:      ThemeId
  brightness:   Brightness
  fontSize:     FontSize
  setThemeId:   (t: ThemeId)    => void
  setBrightness:(b: Brightness) => void
  setFontSize:  (f: FontSize)   => void
}

const ThemeContext = createContext<ThemeState | null>(null)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themeId, setThemeIdState] = useState<ThemeId>(
    () => (localStorage.getItem('app-theme') as ThemeId) || 'ocean'
  )
  const [brightness, setBrightnessState] = useState<Brightness>(
    () => (localStorage.getItem('app-brightness') as Brightness) || 'normal'
  )
  const [fontSize, setFontSizeState] = useState<FontSize>(
    () => (localStorage.getItem('app-font-size') as FontSize) || 'normal'
  )

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', themeId)
    localStorage.setItem('app-theme', themeId)
  }, [themeId])

  useEffect(() => {
    if (brightness === 'normal') {
      document.documentElement.removeAttribute('data-brightness')
      localStorage.removeItem('app-brightness')
    } else {
      document.documentElement.setAttribute('data-brightness', brightness)
      localStorage.setItem('app-brightness', brightness)
    }
  }, [brightness])

  useEffect(() => {
    if (fontSize === 'normal') {
      document.documentElement.removeAttribute('data-font-size')
      localStorage.removeItem('app-font-size')
    } else {
      document.documentElement.setAttribute('data-font-size', fontSize)
      localStorage.setItem('app-font-size', fontSize)
    }
  }, [fontSize])

  const value = useMemo(
    () => ({
      themeId,
      brightness,
      fontSize,
      setThemeId:    setThemeIdState,
      setBrightness: setBrightnessState,
      setFontSize:   setFontSizeState,
    }),
    [themeId, brightness, fontSize]
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider')
  return ctx
}
