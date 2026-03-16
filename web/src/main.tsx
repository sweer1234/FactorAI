import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '@xyflow/react/dist/style.css'
import './index.css'
import App from './App.tsx'
import { WorkspaceProvider } from './context/WorkspaceContext.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <WorkspaceProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </WorkspaceProvider>
  </StrictMode>,
)
