export function formatDate(value: string, language: string) {
  const date = new Date(value.length === 10 ? `${value}T12:00:00Z` : value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(language === 'es' ? 'es-CL' : 'en-GB', {
        dateStyle: 'medium',
        timeZone: 'UTC',
      }).format(date)
}
