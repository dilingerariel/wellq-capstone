/** Production never falls back to synthetic records or the demo role selector. */
export function resolveDataMode(
  configured: string | undefined,
  production: boolean,
): 'api' | 'demo' {
  const mode = configured || (production ? 'api' : 'demo')
  if (mode !== 'demo' && mode !== 'api') throw new Error('VITE_DATA_MODE must be demo or api')
  if (production && mode === 'demo')
    throw new Error('Production requires API mode; synthetic demonstration is development-only')
  return mode
}
