import { useEffect } from 'react'

export function useRtl(title?: string) {
  useEffect(() => {
    const html = document.documentElement
    const prevDir = html.dir
    const prevLang = html.lang
    const prevTitle = document.title
    html.dir = 'rtl'
    html.lang = 'he'
    if (title) document.title = title
    return () => {
      html.dir = prevDir || 'ltr'
      html.lang = prevLang || 'en'
      document.title = prevTitle
    }
  }, [title])
}
