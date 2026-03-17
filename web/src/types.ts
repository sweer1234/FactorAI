export type WorkflowStatus = 'draft' | 'running' | 'published'
export type RunStatus = 'queued' | 'running' | 'success' | 'failed'

export interface Workflow {
  id: string
  name: string
  category: string
  tags: string[]
  status: WorkflowStatus
  updatedAt: string
  lastRun?: string
  description?: string
  sourceTemplateId?: string
  graph: WorkflowGraph
}

export interface Template {
  id: string
  name: string
  description: string
  tags: string[]
  updatedAt: string
  category: string
  graph: WorkflowGraph
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

export interface GraphNode {
  id: string
  label: string
  position: {
    x: number
    y: number
  }
  styleVariant?: 'data' | 'feature' | 'model' | 'factor' | 'backtest' | 'default'
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  animated?: boolean
}

export interface WorkflowGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface RunRecord {
  id: string
  workflowId: string
  workflowName: string
  status: RunStatus
  duration: string
  createdAt: string
  message: string
  logs?: string[]
}

export interface ReportMetric {
  label: string
  value: string
  trend: 'up' | 'down'
}

export interface LayerReturn {
  layer: string
  value: number
}

export interface ReportSnapshot {
  workflowId: string
  workflowName: string
  metrics: ReportMetric[]
  equitySeries: number[]
  layerReturn: LayerReturn[]
  updatedAt: string
}
