
import { useEffect } from 'react'

export function useRtl(pageTitle?: string) {
  useEffect(() => {
    const prevDir = document.documentElement.dir
    const prevLang = document.documentElement.lang
    const prevTitle = document.title

    document.documentElement.dir = 'rtl'
    document.documentElement.lang = 'he'
    if (pageTitle) document.title = pageTitle

    return () => {
      document.documentElement.dir = prevDir || 'ltr'
      document.documentElement.lang = prevLang || 'en'
      document.title = prevTitle
    }
  }, [pageTitle])
}
