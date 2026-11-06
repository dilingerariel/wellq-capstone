import { useEffect, useState } from 'react'
import i18n from '../i18n'
function stored(key: string) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
function store(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* Optional visual preferences only. */
  }
}
export function usePreferences() {
  const [theme, setTheme] = useState(() => (stored('wellq.theme') === 'dark' ? 'dark' : 'light'))
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    store('wellq.theme', theme)
  }, [theme])
  useEffect(() => {
    const language = stored('wellq.language')
    if (language === 'en' || language === 'es') void i18n.changeLanguage(language)
    const update = (lng: string) => {
      document.documentElement.lang = lng
      store('wellq.language', lng)
    }
    i18n.on('languageChanged', update)
    return () => {
      i18n.off('languageChanged', update)
    }
  }, [])
  return { theme, toggleTheme: () => setTheme((t) => (t === 'light' ? 'dark' : 'light')) }
}
