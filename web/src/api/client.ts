import type {
  ObservabilityReport,
  WorkflowAnomalies,
  WorkflowInsights,
  WorkflowAlerts,
  Artifact,
  ContractCompileResult,
  ContractFixAppliedAction,
  ContractFixApplyResult,
  ContractFixRollbackResult,
  ContractFixSuggestion,
  GraphRevision,
  NodeState,
  NodeDefinition,
  ReportSnapshot,
  RunLog,
  RunRecord,
  RunCompare,
  WorkflowTrends,
  SloTemplate,
  SloView,
  Template,
  Workflow,
  WorkflowGraph,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

interface ApiWorkflow {
  id: string
  name: string
  category: string
  tags: string[]
  status: string
  updated_at: string
  last_run?: string | null
  description?: string | null
  source_template_id?: string | null
  slo_profile?: string | null
  slo_overrides?: Record<string, number> | null
  graph: WorkflowGraph
}

interface ApiTemplate {
  id: string
  name: string
  description: string
  tags: string[]
  updated_at: string
  category: string
  official?: boolean
  template_group?: string
  graph: WorkflowGraph
}

interface ApiRun {
  id: string
  workflow_id: string
  workflow_name: string
  status: RunRecord['status']
  duration: string
  created_at: string
  message: string
  logs: string[]
  observability?: Record<string, string | number | boolean | null | object | unknown[]>
}

interface ApiRunLog {
  id: string
  run_id: string
  workflow_id: string
  level: string
  node_id?: string | null
  node_name?: string | null
  error_code?: string | null
  detail?: Record<string, string | number | boolean | null | object | unknown[]> | null
  message: string
  created_at: string
}

interface ApiNodeState {
  id: string
  run_id: string
  workflow_id: string
  node_id: string
  node_name: string
  status: NodeState['status']
  started_at?: string | null
  finished_at?: string | null
  duration_ms: number
  error_code?: string | null
  message: string
}

interface ApiReport {
  workflow_id: string
  workflow_name: string
  metrics: ReportSnapshot['metrics']
  equity_series: number[]
  layer_return: ReportSnapshot['layerReturn']
  updated_at: string
}

interface ApiArtifact {
  id: string
  workflow_id?: string | null
  kind: string
  logical_key?: string
  version?: number
  is_active?: boolean
  parent_artifact_id?: string | null
  file_name: string
  file_size: number
  content_type?: string | null
  sha256?: string | null
  audit?: Record<string, string | number | boolean | null> | null
  created_at: string
}

interface ApiContractIssue {
  code: string
  message: string
  node_id?: string
  edge_id?: string
  detail?: Record<string, unknown>
}

interface ApiContractFixSuggestion {
  issue_code: string
  priority: string
  title: string
  message: string
  proposed_action: string
  patch: Record<string, unknown>
}

interface ApiContractCompile {
  valid: boolean
  strict: boolean
  errors: ApiContractIssue[]
  warnings: ApiContractIssue[]
  suggestions: ApiContractFixSuggestion[]
  node_input_schemas: Record<string, Record<string, Record<string, unknown>>>
  node_output_schemas: Record<string, Record<string, Record<string, unknown>>>
  compiled_at: string
}

interface ApiContractFixAppliedAction {
  index: number
  action: string
  status: 'applied' | 'skipped'
  message: string
  patch: Record<string, unknown>
}

interface ApiContractFixApply {
  workflow: ApiWorkflow
  compile: ApiContractCompile
  applied_actions: ApiContractFixAppliedAction[]
}

interface ApiContractFixRollback {
  workflow: ApiWorkflow
  compile: ApiContractCompile
  restored_revision_id: string
  applied_actions: ApiContractFixAppliedAction[]
}

interface ApiRunCompare {
  workflow_id: string
  run_ids: string[]
  metrics: Record<string, Record<string, string | number | boolean | null>>
}

interface ApiAlertIncident {
  run_id: string
  created_at: string
  status: string
  alerts: Array<Record<string, string | number | boolean | null>>
}

interface ApiWorkflowAlerts {
  workflow_id: string
  window_size: number
  thresholds: Record<string, number>
  total_runs: number
  alert_runs: number
  counts: Record<string, number>
  incidents: ApiAlertIncident[]
}

interface ApiObservabilityRecommendation {
  code: string
  level: string
  message: string
  action: string
}

interface ApiWorkflowInsights {
  workflow_id: string
  window_size: number
  health_score: number
  health_level: string
  pass_rate: number
  alert_runs: number
  total_runs: number
  latest_run_id?: string | null
  latest_summary: Record<string, string | number | boolean | null>
  thresholds: Record<string, number>
  suggested_slo_config?: {
    profile?: string | null
    overrides?: Record<string, number>
    reason?: string | null
  }
  recommendations: ApiObservabilityRecommendation[]
}

interface ApiObservabilityAnomaly {
  run_id: string
  metric_name: string
  value: number
  baseline: number
  z_score: number
  level: string
  status: string
  created_at: string
  message: string
}

interface ApiWorkflowAnomalies {
  workflow_id: string
  window_size: number
  z_threshold: number
  metrics: string[]
  total_runs: number
  anomaly_count: number
  anomaly_by_metric: Record<string, number>
  anomalies: ApiObservabilityAnomaly[]
}

interface ApiObservabilityReport {
  workflow_id: string
  window_size: number
  generated_at: string
  markdown: string
}

interface ApiTrendPoint {
  run_id: string
  created_at: string
  status: string
  value: number
  threshold?: number | null
}

interface ApiWorkflowTrends {
  workflow_id: string
  metrics: string[]
  run_ids: string[]
  thresholds: Record<string, number>
  points: Record<string, ApiTrendPoint[]>
}

interface ApiSloView {
  workflow_id: string
  window_size: number
  thresholds: Record<string, number>
  pass_rate: number
  pass_count: number
  fail_count: number
  runs: Array<Record<string, string | number | boolean | null>>
}

interface ApiSloTemplate {
  workflow_id: string
  workflow_category: string
  profile: string
  reason: string
  thresholds: Record<string, number>
}

interface ApiGraphRevision {
  id: string
  workflow_id: string
  revision_no: number
  source: string
  meta: Record<string, unknown>
  created_at: string
}

function toWorkflow(item: ApiWorkflow): Workflow {
  return {
    id: item.id,
    name: item.name,
    category: item.category,
    tags: item.tags,
    status: item.status as Workflow['status'],
    updatedAt: item.updated_at,
    lastRun: item.last_run ?? undefined,
    description: item.description ?? undefined,
    sourceTemplateId: item.source_template_id ?? undefined,
    sloProfile: item.slo_profile ?? undefined,
    sloOverrides: item.slo_overrides ?? undefined,
    graph: item.graph ?? { nodes: [], edges: [] },
  }
}

function toTemplate(item: ApiTemplate): Template {
  return {
    id: item.id,
    name: item.name,
    description: item.description,
    tags: item.tags,
    updatedAt: item.updated_at,
    category: item.category,
    official: item.official ?? true,
    templateGroup: item.template_group ?? '官方模板',
    graph: item.graph ?? { nodes: [], edges: [] },
  }
}

function toRun(item: ApiRun): RunRecord {
  return {
    id: item.id,
    workflowId: item.workflow_id,
    workflowName: item.workflow_name,
    status: item.status,
    duration: item.duration,
    createdAt: item.created_at,
    message: item.message,
    logs: item.logs,
    observability: item.observability ?? undefined,
  }
}

function toRunLog(item: ApiRunLog): RunLog {
  return {
    id: item.id,
    runId: item.run_id,
    workflowId: item.workflow_id,
    level: item.level,
    nodeId: item.node_id ?? undefined,
    nodeName: item.node_name ?? undefined,
    errorCode: item.error_code ?? undefined,
    detail: item.detail ?? undefined,
    message: item.message,
    createdAt: item.created_at,
  }
}

function toNodeState(item: ApiNodeState): NodeState {
  return {
    id: item.id,
    runId: item.run_id,
    workflowId: item.workflow_id,
    nodeId: item.node_id,
    nodeName: item.node_name,
    status: item.status,
    startedAt: item.started_at ?? undefined,
    finishedAt: item.finished_at ?? undefined,
    durationMs: item.duration_ms,
    errorCode: item.error_code ?? undefined,
    message: item.message,
  }
}

function toArtifact(item: ApiArtifact): Artifact {
  return {
    id: item.id,
    workflowId: item.workflow_id ?? undefined,
    kind: item.kind,
    logicalKey: item.logical_key ?? undefined,
    version: item.version ?? undefined,
    isActive: item.is_active ?? undefined,
    parentArtifactId: item.parent_artifact_id ?? undefined,
    fileName: item.file_name,
    fileSize: item.file_size,
    contentType: item.content_type ?? undefined,
    sha256: item.sha256 ?? undefined,
    audit: item.audit ?? undefined,
    createdAt: item.created_at,
  }
}

function toContractIssue(item: ApiContractIssue) {
  const detail =
    (item.detail as Record<string, string | number | boolean | null | object | unknown[]>) ?? {}
  return {
    code: item.code,
    message: item.message,
    nodeId: item.node_id ?? undefined,
    edgeId: item.edge_id ?? undefined,
    detail,
  }
}

function toContractFixSuggestion(item: ApiContractFixSuggestion): ContractFixSuggestion {
  return {
    issueCode: item.issue_code,
    priority: item.priority,
    title: item.title,
    message: item.message,
    proposedAction: item.proposed_action,
    patch: item.patch as Record<string, string | number | boolean | null | object | unknown[]>,
  }
}

function toContractCompile(item: ApiContractCompile): ContractCompileResult {
  return {
    valid: item.valid,
    strict: item.strict,
    errors: item.errors.map(toContractIssue),
    warnings: item.warnings.map(toContractIssue),
    suggestions: item.suggestions.map(toContractFixSuggestion),
    nodeInputSchemas: item.node_input_schemas,
    nodeOutputSchemas: item.node_output_schemas,
    compiledAt: item.compiled_at,
  }
}

function toContractFixAppliedAction(item: ApiContractFixAppliedAction): ContractFixAppliedAction {
  return {
    index: item.index,
    action: item.action,
    status: item.status,
    message: item.message,
    patch: item.patch as Record<string, string | number | boolean | null | object | unknown[]>,
  }
}

function toContractFixApply(item: ApiContractFixApply): ContractFixApplyResult {
  return {
    workflow: toWorkflow(item.workflow),
    compile: toContractCompile(item.compile),
    appliedActions: item.applied_actions.map(toContractFixAppliedAction),
  }
}

function toContractFixRollback(item: ApiContractFixRollback): ContractFixRollbackResult {
  return {
    workflow: toWorkflow(item.workflow),
    compile: toContractCompile(item.compile),
    restoredRevisionId: item.restored_revision_id,
    appliedActions: item.applied_actions.map(toContractFixAppliedAction),
  }
}

function toRunCompare(item: ApiRunCompare): RunCompare {
  return {
    workflowId: item.workflow_id,
    runIds: item.run_ids,
    metrics: item.metrics,
  }
}

function toWorkflowAlerts(item: ApiWorkflowAlerts): WorkflowAlerts {
  return {
    workflowId: item.workflow_id,
    windowSize: item.window_size,
    thresholds: item.thresholds,
    totalRuns: item.total_runs,
    alertRuns: item.alert_runs,
    counts: item.counts,
    incidents: item.incidents.map((incident) => ({
      runId: incident.run_id,
      createdAt: incident.created_at,
      status: incident.status,
      alerts: incident.alerts,
    })),
  }
}

function toWorkflowInsights(item: ApiWorkflowInsights): WorkflowInsights {
  return {
    workflowId: item.workflow_id,
    windowSize: item.window_size,
    healthScore: item.health_score,
    healthLevel: item.health_level,
    passRate: item.pass_rate,
    alertRuns: item.alert_runs,
    totalRuns: item.total_runs,
    latestRunId: item.latest_run_id ?? undefined,
    latestSummary: item.latest_summary,
    thresholds: item.thresholds,
    suggestedSloConfig: {
      profile: item.suggested_slo_config?.profile ?? undefined,
      overrides: item.suggested_slo_config?.overrides ?? {},
      reason: item.suggested_slo_config?.reason ?? undefined,
    },
    recommendations: item.recommendations.map((rec) => ({
      code: rec.code,
      level: rec.level,
      message: rec.message,
      action: rec.action,
    })),
  }
}

function toWorkflowAnomalies(item: ApiWorkflowAnomalies): WorkflowAnomalies {
  return {
    workflowId: item.workflow_id,
    windowSize: item.window_size,
    zThreshold: item.z_threshold,
    metrics: item.metrics,
    totalRuns: item.total_runs,
    anomalyCount: item.anomaly_count,
    anomalyByMetric: item.anomaly_by_metric,
    anomalies: item.anomalies.map((anomaly) => ({
      runId: anomaly.run_id,
      metricName: anomaly.metric_name,
      value: Number(anomaly.value ?? 0),
      baseline: Number(anomaly.baseline ?? 0),
      zScore: Number(anomaly.z_score ?? 0),
      level: anomaly.level,
      status: anomaly.status,
      createdAt: anomaly.created_at,
      message: anomaly.message,
    })),
  }
}

function toObservabilityReport(item: ApiObservabilityReport): ObservabilityReport {
  return {
    workflowId: item.workflow_id,
    windowSize: item.window_size,
    generatedAt: item.generated_at,
    markdown: item.markdown,
  }
}

function toWorkflowTrends(item: ApiWorkflowTrends): WorkflowTrends {
  return {
    workflowId: item.workflow_id,
    metrics: item.metrics,
    runIds: item.run_ids,
    thresholds: item.thresholds,
    points: Object.fromEntries(
      Object.entries(item.points).map(([metricName, rows]) => [
        metricName,
        rows.map((row) => ({
          runId: row.run_id,
          createdAt: row.created_at,
          status: row.status,
          value: Number(row.value ?? 0),
          threshold: typeof row.threshold === 'number' ? row.threshold : undefined,
        })),
      ]),
    ),
  }
}

function toSloTemplate(item: ApiSloTemplate): SloTemplate {
  return {
    workflowId: item.workflow_id,
    workflowCategory: item.workflow_category,
    profile: item.profile,
    reason: item.reason,
    thresholds: item.thresholds,
  }
}

function toGraphRevision(item: ApiGraphRevision): GraphRevision {
  return {
    id: item.id,
    workflowId: item.workflow_id,
    revisionNo: item.revision_no,
    source: item.source,
    meta: item.meta as Record<string, string | number | boolean | null | object | unknown[]>,
    createdAt: item.created_at,
  }
}

function toSloView(item: ApiSloView): SloView {
  return {
    workflowId: item.workflow_id,
    windowSize: item.window_size,
    thresholds: item.thresholds,
    passRate: item.pass_rate,
    passCount: item.pass_count,
    failCount: item.fail_count,
    runs: item.runs,
  }
}

function toReport(item: ApiReport): ReportSnapshot {
  return {
    workflowId: item.workflow_id,
    workflowName: item.workflow_name,
    metrics: item.metrics,
    equitySeries: item.equity_series,
    layerReturn: item.layer_return,
    updatedAt: item.updated_at,
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API ${response.status}: ${text}`)
  }
  if (response.status === 204) return null as T
  return (await response.json()) as T
}

export async function fetchWorkflows() {
  const data = await request<ApiWorkflow[]>('/workflows')
  return data.map(toWorkflow)
}

export async function fetchTemplates(params?: { official?: boolean; keyword?: string }) {
  const query = new URLSearchParams()
  if (typeof params?.official === 'boolean') query.set('official', String(params.official))
  if (params?.keyword) query.set('keyword', params.keyword)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiTemplate[]>(`/templates${suffix}`)
  return data.map(toTemplate)
}

export async function fetchRuns() {
  const data = await request<ApiRun[]>('/runs')
  return data.map(toRun)
}

export async function fetchNodeLibrary() {
  return request<NodeDefinition[]>('/node-specs')
}

export async function fetchNodeSpec(nodeId: string) {
  return request<NodeDefinition>(`/node-specs/${nodeId}`)
}

export async function createWorkflow(payload: {
  name: string
  category: string
  tags: string[]
  description?: string
  graph?: WorkflowGraph
  sourceTemplateId?: string
}) {
  const data = await request<ApiWorkflow>('/workflows', {
    method: 'POST',
    body: JSON.stringify({
      name: payload.name,
      category: payload.category,
      tags: payload.tags,
      description: payload.description,
      graph: payload.graph,
      source_template_id: payload.sourceTemplateId,
    }),
  })
  return toWorkflow(data)
}

export async function cloneTemplate(templateId: string) {
  const data = await request<ApiWorkflow>(`/templates/${templateId}/clone`, {
    method: 'POST',
  })
  return toWorkflow(data)
}

export async function saveWorkflowGraph(workflowId: string, graph: WorkflowGraph) {
  const data = await request<ApiWorkflow>(`/workflows/${workflowId}/graph`, {
    method: 'PUT',
    body: JSON.stringify({ graph }),
  })
  return toWorkflow(data)
}

export async function saveWorkflowGraphStrict(workflowId: string, graph: WorkflowGraph) {
  const data = await request<ApiWorkflow>(`/workflows/${workflowId}/graph?strict_contract=true`, {
    method: 'PUT',
    body: JSON.stringify({ graph }),
  })
  return toWorkflow(data)
}

export async function saveWorkflowDraft(workflowId: string) {
  const data = await request<ApiWorkflow>(`/workflows/${workflowId}/draft`, {
    method: 'POST',
  })
  return toWorkflow(data)
}

export async function runWorkflow(workflowId: string) {
  const data = await request<ApiRun>(`/workflows/${workflowId}/run`, {
    method: 'POST',
  })
  return toRun(data)
}

export async function fetchReport(workflowId: string) {
  const data = await request<ApiReport | null>(`/reports/${workflowId}`)
  return data ? toReport(data) : undefined
}

export async function fetchRunLogs(runId: string) {
  const data = await request<ApiRunLog[]>(`/runs/${runId}/logs`)
  return data.map(toRunLog)
}

export async function fetchRunNodeStates(runId: string) {
  const data = await request<ApiNodeState[]>(`/runs/${runId}/node-states`)
  return data.map(toNodeState)
}

export async function fetchArtifacts(params?: {
  workflowId?: string
  kind?: string
  logicalKey?: string
  activeOnly?: boolean
}) {
  const query = new URLSearchParams()
  if (params?.workflowId) query.set('workflow_id', params.workflowId)
  if (params?.kind) query.set('kind', params.kind)
  if (params?.logicalKey) query.set('logical_key', params.logicalKey)
  if (typeof params?.activeOnly === 'boolean') query.set('active_only', String(params.activeOnly))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiArtifact[]>(`/artifacts${suffix}`)
  return data.map(toArtifact)
}

export async function uploadArtifact(payload: {
  file: File
  kind?: string
  workflowId?: string
  logicalKey?: string
  activate?: boolean
}) {
  const form = new FormData()
  form.append('file', payload.file)
  if (payload.kind) form.append('kind', payload.kind)
  if (payload.workflowId) form.append('workflow_id', payload.workflowId)
  if (payload.logicalKey) form.append('logical_key', payload.logicalKey)
  if (typeof payload.activate === 'boolean') form.append('activate', String(payload.activate))

  const response = await fetch(`${API_BASE}/artifacts/upload`, {
    method: 'POST',
    body: form,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API ${response.status}: ${text}`)
  }
  const data = (await response.json()) as ApiArtifact
  return toArtifact(data)
}

export async function rollbackArtifact(artifactId: string, reason?: string) {
  const data = await request<ApiArtifact>(`/artifacts/${artifactId}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
  return toArtifact(data)
}

export async function fetchWorkflowContractCompile(workflowId: string, strict = false) {
  const data = await request<ApiContractCompile>(
    `/workflows/${workflowId}/contract-compile?strict=${String(strict)}`,
  )
  return toContractCompile(data)
}

export async function fetchWorkflowContractFixSuggestions(workflowId: string, strict = false) {
  const data = await request<ApiContractFixSuggestion[]>(
    `/workflows/${workflowId}/contract-fix-suggestions?strict=${String(strict)}`,
  )
  return data.map(toContractFixSuggestion)
}

export async function applyWorkflowContractFixes(
  workflowId: string,
  payload?: { strict?: boolean; suggestionIndexes?: number[]; maxActions?: number },
) {
  const data = await request<ApiContractFixApply>(`/workflows/${workflowId}/contract-fix-apply`, {
    method: 'POST',
    body: JSON.stringify({
      strict: payload?.strict ?? false,
      suggestion_indexes: payload?.suggestionIndexes ?? [],
      max_actions: payload?.maxActions ?? 20,
    }),
  })
  return toContractFixApply(data)
}

export async function rollbackWorkflowContractFixes(workflowId: string, revisionId?: string) {
  const data = await request<ApiContractFixRollback>(`/workflows/${workflowId}/contract-fix-rollback`, {
    method: 'POST',
    body: JSON.stringify({ revision_id: revisionId ?? null }),
  })
  return toContractFixRollback(data)
}

export async function fetchWorkflowGraphRevisions(
  workflowId: string,
  params?: { source?: string; limit?: number },
) {
  const query = new URLSearchParams()
  if (params?.source) query.set('source', params.source)
  if (params?.limit) query.set('limit', String(params.limit))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiGraphRevision[]>(`/workflows/${workflowId}/graph-revisions${suffix}`)
  return data.map(toGraphRevision)
}

export async function fetchWorkflowRunCompare(workflowId: string, runIds?: string[]) {
  const query = new URLSearchParams()
  if (runIds && runIds.length > 0) query.set('run_ids', runIds.join(','))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiRunCompare>(`/workflows/${workflowId}/observability/compare${suffix}`)
  return toRunCompare(data)
}

export async function fetchWorkflowTrends(
  workflowId: string,
  params?: {
    metrics?: string[]
    windowSize?: number
    useTemplate?: boolean
    profile?: string
    p95NodeDurationMs?: number
    failedNodes?: number
    warnLogs?: number
    errorLogs?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.metrics && params.metrics.length > 0) query.set('metrics', params.metrics.join(','))
  if (params?.windowSize) query.set('window_size', String(params.windowSize))
  if (typeof params?.useTemplate === 'boolean') query.set('use_template', String(params.useTemplate))
  if (params?.profile) query.set('profile', params.profile)
  if (params?.p95NodeDurationMs) query.set('p95_node_duration_ms', String(params.p95NodeDurationMs))
  if (typeof params?.failedNodes === 'number') query.set('failed_nodes', String(params.failedNodes))
  if (typeof params?.warnLogs === 'number') query.set('warn_logs', String(params.warnLogs))
  if (typeof params?.errorLogs === 'number') query.set('error_logs', String(params.errorLogs))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiWorkflowTrends>(`/workflows/${workflowId}/observability/trends${suffix}`)
  return toWorkflowTrends(data)
}

export async function fetchWorkflowAlerts(
  workflowId: string,
  params?: {
    windowSize?: number
    useTemplate?: boolean
    profile?: string
    p95NodeDurationMs?: number
    failedNodes?: number
    warnLogs?: number
    errorLogs?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.windowSize) query.set('window_size', String(params.windowSize))
  if (typeof params?.useTemplate === 'boolean') query.set('use_template', String(params.useTemplate))
  if (params?.profile) query.set('profile', params.profile)
  if (params?.p95NodeDurationMs) query.set('p95_node_duration_ms', String(params.p95NodeDurationMs))
  if (typeof params?.failedNodes === 'number') query.set('failed_nodes', String(params.failedNodes))
  if (typeof params?.warnLogs === 'number') query.set('warn_logs', String(params.warnLogs))
  if (typeof params?.errorLogs === 'number') query.set('error_logs', String(params.errorLogs))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiWorkflowAlerts>(`/workflows/${workflowId}/observability/alerts${suffix}`)
  return toWorkflowAlerts(data)
}

export async function fetchWorkflowInsights(
  workflowId: string,
  params?: {
    windowSize?: number
    useTemplate?: boolean
    profile?: string
    p95NodeDurationMs?: number
    failedNodes?: number
    warnLogs?: number
    errorLogs?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.windowSize) query.set('window_size', String(params.windowSize))
  if (typeof params?.useTemplate === 'boolean') query.set('use_template', String(params.useTemplate))
  if (params?.profile) query.set('profile', params.profile)
  if (params?.p95NodeDurationMs) query.set('p95_node_duration_ms', String(params.p95NodeDurationMs))
  if (typeof params?.failedNodes === 'number') query.set('failed_nodes', String(params.failedNodes))
  if (typeof params?.warnLogs === 'number') query.set('warn_logs', String(params.warnLogs))
  if (typeof params?.errorLogs === 'number') query.set('error_logs', String(params.errorLogs))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiWorkflowInsights>(`/workflows/${workflowId}/observability/insights${suffix}`)
  return toWorkflowInsights(data)
}

export async function fetchWorkflowAnomalies(
  workflowId: string,
  params?: {
    metrics?: string[]
    windowSize?: number
    zThreshold?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.metrics && params.metrics.length > 0) query.set('metrics', params.metrics.join(','))
  if (params?.windowSize) query.set('window_size', String(params.windowSize))
  if (typeof params?.zThreshold === 'number') query.set('z_threshold', String(params.zThreshold))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiWorkflowAnomalies>(`/workflows/${workflowId}/observability/anomalies${suffix}`)
  return toWorkflowAnomalies(data)
}

export async function fetchWorkflowInsightsReport(
  workflowId: string,
  params?: {
    windowSize?: number
    useTemplate?: boolean
    zThreshold?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.windowSize) query.set('window_size', String(params.windowSize))
  if (typeof params?.useTemplate === 'boolean') query.set('use_template', String(params.useTemplate))
  if (typeof params?.zThreshold === 'number') query.set('z_threshold', String(params.zThreshold))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiObservabilityReport>(`/workflows/${workflowId}/observability/insights-report${suffix}`)
  return toObservabilityReport(data)
}

export async function fetchWorkflowSloView(
  workflowId: string,
  params?: {
    windowSize?: number
    useTemplate?: boolean
    profile?: string
    p95NodeDurationMs?: number
    failedNodes?: number
    warnLogs?: number
    errorLogs?: number
  },
) {
  const query = new URLSearchParams()
  if (params?.windowSize) query.set('window_size', String(params.windowSize))
  if (typeof params?.useTemplate === 'boolean') query.set('use_template', String(params.useTemplate))
  if (params?.profile) query.set('profile', params.profile)
  if (params?.p95NodeDurationMs) query.set('p95_node_duration_ms', String(params.p95NodeDurationMs))
  if (typeof params?.failedNodes === 'number') query.set('failed_nodes', String(params.failedNodes))
  if (typeof params?.warnLogs === 'number') query.set('warn_logs', String(params.warnLogs))
  if (typeof params?.errorLogs === 'number') query.set('error_logs', String(params.errorLogs))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiSloView>(`/workflows/${workflowId}/observability/slo${suffix}`)
  return toSloView(data)
}

export async function fetchWorkflowSloTemplate(workflowId: string, profile?: string) {
  const query = new URLSearchParams()
  if (profile) query.set('profile', profile)
  const suffix = query.toString() ? `?${query.toString()}` : ''
  const data = await request<ApiSloTemplate>(`/workflows/${workflowId}/observability/slo-template${suffix}`)
  return toSloTemplate(data)
}

export async function updateWorkflowSloConfig(
  workflowId: string,
  payload: { profile?: string | null; overrides?: Record<string, number> },
) {
  const data = await request<ApiSloTemplate>(`/workflows/${workflowId}/observability/slo-config`, {
    method: 'PUT',
    body: JSON.stringify({
      profile: payload.profile ?? null,
      overrides: payload.overrides ?? {},
    }),
  })
  return toSloTemplate(data)
}

export async function fetchBootstrap() {
  const [workflows, templates, runs, nodeLibrary] = await Promise.all([
    fetchWorkflows(),
    fetchTemplates({ official: true }),
    fetchRuns(),
    fetchNodeLibrary(),
  ])
  return { workflows, templates, runs, nodeLibrary }
}
