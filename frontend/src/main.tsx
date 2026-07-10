import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { FieldConfigProvider } from './context/FieldConfigContext'
import App, { AppErrorBoundary } from './App'

const rootEl = document.getElementById('root')
if (!rootEl) {
  document.body.innerHTML = '<div style="padding:2rem;font-family:system-ui;">Missing #root element. Check index.html.</div>'
} else {
  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <AppErrorBoundary>
        <ThemeProvider>
          <AuthProvider>
            <FieldConfigProvider>
              <App />
            </FieldConfigProvider>
          </AuthProvider>
        </ThemeProvider>
      </AppErrorBoundary>
    </React.StrictMode>
  )
}
