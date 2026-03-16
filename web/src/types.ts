export type WorkflowStatus = 'draft' | 'running' | 'published'

export interface Workflow {
  id: string
  name: string
  category: string
  tags: string[]
  status: WorkflowStatus
  updatedAt: string
  lastRun?: string
}

export interface Template {
  id: string
  name: string
  description: string
  tags: string[]
  updatedAt: string
}

export interface NodeDefinition {
  id: string
  name: string
  category: string
  description: string
  inputs: string[]
  outputs: string[]
  params: Array<{
    key: string
    type: 'string' | 'number' | 'boolean' | 'select'
    required?: boolean
    defaultValue?: string | number | boolean
    options?: string[]
  }>
}

export interface RunRecord {
  id: string
  workflowName: string
  status: 'queued' | 'running' | 'success' | 'failed'
  duration: string
  createdAt: string
  message: string
}

export interface ReportMetric {
  label: string
  value: string
  trend: 'up' | 'down'
}
