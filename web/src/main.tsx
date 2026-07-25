import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './i18n'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: 'rgba(15,23,42,0.95)',
            color: '#e5e7eb',
            border: '1px solid rgba(255,255,255,0.1)',
            backdropFilter: 'blur(12px)',
            borderRadius: '12px',
            fontSize: '13px',
            padding: '10px 14px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          },
          success: { iconTheme: { primary: '#10B981', secondary: '#0f172a' } },
          error: { iconTheme: { primary: '#EF4444', secondary: '#0f172a' } },
          loading: { iconTheme: { primary: '#06B6D4', secondary: '#0f172a' } },
        }}
      />
    </BrowserRouter>
  </React.StrictMode>,
)
