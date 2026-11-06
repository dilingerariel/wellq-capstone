import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './i18n'
import './styles/global.css'
import { App } from './app/App'
import { RuntimeProvider } from './app/runtime'
import { ErrorBoundary } from './app/ErrorBoundary'
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <RuntimeProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </RuntimeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)
