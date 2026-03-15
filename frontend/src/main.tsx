import React from 'react'
import ReactDOM from 'react-dom/client'

// Global base font size increase
const style = document.createElement('style')
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; }
  html { font-size: 24px; }
  body { margin: 0; font-family: system-ui, -apple-system, sans-serif; }
`
document.head.appendChild(style)
import { AuthProvider } from './context/AuthContext'
import App, { AppErrorBoundary } from './App'

const rootEl = document.getElementById('root')
if (!rootEl) {
  document.body.innerHTML = '<div style="padding:2rem;font-family:system-ui;">Missing #root element. Check index.html.</div>'
} else {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <AppErrorBoundary>
        <AuthProvider>
          <App />
        </AuthProvider>
      </AppErrorBoundary>
    </React.StrictMode>
  )
}
