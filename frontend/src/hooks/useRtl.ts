import { useEffect } from 'react';

export function useRtl(language: 'he' | 'en' = 'he') {
  useEffect(() => {
    const isRtl = language === 'he';
    document.documentElement.dir = isRtl ? 'rtl' : 'ltr';
    document.documentElement.lang = language;
    document.body.classList.toggle('rtl-app', isRtl);
    return () => {
      document.body.classList.remove('rtl-app');
    };
  }, [language]);
}
