import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './App.css'
import './workspace.css'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary.tsx'

document.documentElement.dataset.theme = localStorage.getItem('odin-theme') === 'dark' ? 'dark' : 'light'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
