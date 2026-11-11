// Development-only integration host. No credentials or signing keys in this file.
export function localIdentity({
  professionalLogin = false,
  apiTarget = 'http://127.0.0.1:8765',
} = {}) {
  if (professionalLogin && apiTarget !== 'http://127.0.0.1:8765')
    throw new Error('Professional synthetic login requires the existing loopback bridge')
  return {
    name: 'wellq-local-synthetic-identity',
    apply: 'serve',
    configResolved(config) {
      if (config.isProduction) throw new Error('Synthetic identity requires a development server')
    },
    transformIndexHtml() {
      return [
        {
          tag: 'script',
          attrs: {
            src: '/__wellq_local/adapter.js',
            'data-wellq-entry': professionalLogin ? 'clinician' : 'legacy',
          },
          injectTo: 'head-prepend',
        },
      ]
    },
  }
}
