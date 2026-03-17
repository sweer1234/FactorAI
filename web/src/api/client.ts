import type {
  NodeDefinition,
  ReportSnapshot,
  RunRecord,
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
  graph: WorkflowGraph
}

interface ApiTemplate {
  id: string
  name: string
  description: string
  tags: string[]
  updated_at: string
  category: string
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
}

interface ApiReport {
  workflow_id: string
  workflow_name: string
  metrics: ReportSnapshot['metrics']
  equity_series: number[]
  layer_return: ReportSnapshot['layerReturn']
  updated_at: string
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

export async function fetchTemplates() {
  const data = await request<ApiTemplate[]>('/templates')
  return data.map(toTemplate)
}

export async function fetchRuns() {
  const data = await request<ApiRun[]>('/runs')
  return data.map(toRun)
}

export async function fetchNodeLibrary() {
  return request<NodeDefinition[]>('/node-library')
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

export async function fetchBootstrap() {
  const [workflows, templates, runs, nodeLibrary] = await Promise.all([
    fetchWorkflows(),
    fetchTemplates(),
    fetchRuns(),
    fetchNodeLibrary(),
  ])
  return { workflows, templates, runs, nodeLibrary }
}
