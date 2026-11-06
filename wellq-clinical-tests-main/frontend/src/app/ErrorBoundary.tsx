import { Component, type ReactNode } from 'react'
import i18n from '../i18n'
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? (
      <main className="state" role="alert">
        <h1>{i18n.t('configurationError')}</h1>
      </main>
    ) : (
      this.props.children
    )
  }
}
