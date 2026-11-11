import type { HtmlTagDescriptor, ResolvedConfig } from 'vite'
export function localIdentity(options?: { professionalLogin?: boolean; apiTarget?: string }): {
  name: string
  apply: 'serve'
  configResolved(config: Pick<ResolvedConfig, 'isProduction'>): void
  transformIndexHtml(): HtmlTagDescriptor[]
}
