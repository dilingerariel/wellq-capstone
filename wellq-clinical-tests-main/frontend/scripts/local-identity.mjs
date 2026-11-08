// Development-only integration host. No credentials or signing keys in this file.
export function localIdentity() {
  return {
    name: 'wellq-local-synthetic-identity',
    apply: 'serve',
    transformIndexHtml() {
      return [
        {
          tag: 'script',
          attrs: { src: '/__wellq_local/adapter.js' },
          injectTo: 'head-prepend',
        },
      ]
    },
  }
}
