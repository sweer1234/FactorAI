import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { EditorPage } from './pages/EditorPage'
import { LandingPage } from './pages/LandingPage'
import { ReportsPage } from './pages/ReportsPage'
import { RunsPage } from './pages/RunsPage'
import { TemplatesPage } from './pages/TemplatesPage'
import { WorkflowsPage } from './pages/WorkflowsPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route element={<AppShell />}>
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/editor/:workflowId" element={<EditorPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/reports/:workflowId" element={<ReportsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
