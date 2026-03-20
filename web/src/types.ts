export type WorkflowStatus = 'draft' | 'running' | 'published'
export type RunStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled'

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
  sloProfile?: string
  sloOverrides?: Record<string, number>
  graph: WorkflowGraph
}

export interface Template {
  id: string
  name: string
  description: string
  tags: string[]
  updatedAt: string
  category: string
  official?: boolean
  templateGroup?: string
  graph: WorkflowGraph
}

export interface TemplateVersion {
  id: string
  templateId: string
  version: string
  changelog: string
  graph: WorkflowGraph
  createdAt: string
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
  doc?: {
    intro?: string
    workflow_example?: string
    notes?: string[]
  }
  runtime?: {
    engine?: string
    timeout_sec?: number
    memory_mb?: number
  }
}

export interface GraphNode {
  id: string
  label: string
  position: {
    x: number
    y: number
  }
  styleVariant?: 'data' | 'feature' | 'model' | 'factor' | 'backtest' | 'default'
  nodeSpecId?: string
  params?: Record<string, string | number | boolean>
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
  observability?: Record<string, string | number | boolean | null | object | unknown[]>
  cancelRequested?: boolean
  retriedFromRunId?: string
}

export interface RunLog {
  id: string
  runId: string
  workflowId: string
  level: string
  nodeId?: string
  nodeName?: string
  errorCode?: string
  detail?: Record<string, string | number | boolean | null | unknown[] | object>
  message: string
  createdAt: string
}

export interface NodeState {
  id: string
  runId: string
  workflowId: string
  nodeId: string
  nodeName: string
  status: 'queued' | 'running' | 'success' | 'failed'
  startedAt?: string
  finishedAt?: string
  durationMs: number
  errorCode?: string
  message: string
}

export interface Artifact {
  id: string
  workflowId?: string
  kind: string
  logicalKey?: string
  version?: number
  isActive?: boolean
  parentArtifactId?: string
  fileName: string
  fileSize: number
  contentType?: string
  sha256?: string
  audit?: Record<string, string | number | boolean | null>
  createdAt: string
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

export interface ContractIssue {
  code: string
  message: string
  nodeId?: string
  edgeId?: string
  detail: Record<string, string | number | boolean | null | object | unknown[]>
}

export interface ContractFixSuggestion {
  issueCode: string
  priority: string
  title: string
  message: string
  proposedAction: string
  patch: Record<string, string | number | boolean | null | object | unknown[]>
}

export interface ContractCompileResult {
  valid: boolean
  strict: boolean
  errors: ContractIssue[]
  warnings: ContractIssue[]
  suggestions: ContractFixSuggestion[]
  nodeInputSchemas: Record<string, Record<string, Record<string, unknown>>>
  nodeOutputSchemas: Record<string, Record<string, Record<string, unknown>>>
  compiledAt: string
}

export interface ContractFixAppliedAction {
  index: number
  action: string
  status: 'applied' | 'skipped'
  message: string
  patch: Record<string, string | number | boolean | null | object | unknown[]>
}

export interface ContractFixApplyResult {
  workflow: Workflow
  compile: ContractCompileResult
  appliedActions: ContractFixAppliedAction[]
}

export interface ContractFixRollbackResult {
  workflow: Workflow
  compile: ContractCompileResult
  restoredRevisionId: string
  appliedActions: ContractFixAppliedAction[]
}

export interface RunCompare {
  workflowId: string
  runIds: string[]
  metrics: Record<string, Record<string, string | number | boolean | null>>
}

export interface TrendPoint {
  runId: string
  createdAt: string
  status: string
  value: number
  threshold?: number
}

export interface WorkflowTrends {
  workflowId: string
  metrics: string[]
  runIds: string[]
  thresholds: Record<string, number>
  points: Record<string, TrendPoint[]>
}

export interface AlertIncident {
  runId: string
  createdAt: string
  status: string
  alerts: Array<Record<string, string | number | boolean | null>>
}

export interface WorkflowAlerts {
  workflowId: string
  windowSize: number
  thresholds: Record<string, number>
  totalRuns: number
  alertRuns: number
  counts: Record<string, number>
  incidents: AlertIncident[]
}

export interface ObservabilityRecommendation {
  code: string
  level: string
  message: string
  action: string
}

export interface WorkflowInsights {
  workflowId: string
  windowSize: number
  healthScore: number
  healthLevel: string
  passRate: number
  alertRuns: number
  totalRuns: number
  latestRunId?: string
  latestSummary: Record<string, string | number | boolean | null>
  thresholds: Record<string, number>
  suggestedSloConfig: {
    profile?: string
    overrides: Record<string, number>
    reason?: string
  }
  recommendations: ObservabilityRecommendation[]
}

export interface ObservabilityAnomaly {
  runId: string
  metricName: string
  value: number
  baseline: number
  zScore: number
  level: string
  status: string
  createdAt: string
  message: string
}

export interface WorkflowAnomalies {
  workflowId: string
  windowSize: number
  zThreshold: number
  metrics: string[]
  totalRuns: number
  anomalyCount: number
  anomalyByMetric: Record<string, number>
  anomalies: ObservabilityAnomaly[]
}

export interface ObservabilityReport {
  workflowId: string
  windowSize: number
  generatedAt: string
  markdown: string
}

export interface SloView {
  workflowId: string
  windowSize: number
  thresholds: Record<string, number>
  passRate: number
  passCount: number
  failCount: number
  runs: Array<Record<string, string | number | boolean | null>>
}

export interface SloTemplate {
  workflowId: string
  workflowCategory: string
  profile: string
  reason: string
  thresholds: Record<string, number>
}

export interface GraphRevision {
  id: string
  workflowId: string
  revisionNo: number
  source: string
  meta: Record<string, string | number | boolean | null | object | unknown[]>
  createdAt: string
}
