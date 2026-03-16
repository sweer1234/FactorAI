/* eslint-disable react-refresh/only-export-components */
import { createContext, useEffect, useState, type ReactNode } from 'react'
import { nodeLibrary, runRecords, seededGraphs, seededReports, templates, workflowList } from '../data/mock'
import type {
  ReportMetric,
  ReportSnapshot,
  RunRecord,
  RunStatus,
  Template,
  Workflow,
  WorkflowGraph,
} from '../types'

const STORAGE_KEY = 'factorlab.workspace.v2'

interface WorkspaceStore {
  workflows: Workflow[]
  templates: Template[]
  runs: RunRecord[]
  nodeLibrary: typeof nodeLibrary
  reports: Record<string, ReportSnapshot>
  getGraphByWorkflowId: (workflowId: string) => WorkflowGraph | undefined
  createWorkflow: (payload: {
    name: string
    category: string
    tags: string[]
    description?: string
    graph?: WorkflowGraph
    sourceTemplateId?: string
  }) => string
  cloneTemplate: (templateId: string) => string | null
  saveWorkflowGraph: (workflowId: string, graph: WorkflowGraph) => void
  saveWorkflowDraft: (workflowId: string) => void
  runWorkflow: (workflowId: string) => void
  getReportByWorkflowId: (workflowId: string) => ReportSnapshot | undefined
  notice: string | null
}

interface PersistedState {
  workflows: Workflow[]
  runs: RunRecord[]
  graphs: Record<string, WorkflowGraph>
  reports: Record<string, ReportSnapshot>
}

export const WorkspaceContext = createContext<WorkspaceStore | null>(null)

function nowText() {
  const dt = new Date()
  const p = (num: number) => String(num).padStart(2, '0')
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())} ${p(dt.getHours())}:${p(dt.getMinutes())}:${p(dt.getSeconds())}`
}

function createDuration(startedAt: number) {
  const elapsed = Math.max(1, Math.round((Date.now() - startedAt) / 1000))
  const min = Math.floor(elapsed / 60)
  const sec = elapsed % 60
  return `${String(min).padStart(2, '0')}m ${String(sec).padStart(2, '0')}s`
}

function cloneGraph(graph?: WorkflowGraph): WorkflowGraph {
  return {
    nodes: (graph?.nodes ?? []).map((item) => ({ ...item, position: { ...item.position } })),
    edges: (graph?.edges ?? []).map((item) => ({ ...item })),
  }
}

function generateRunId() {
  return `run-${Math.random().toString(36).slice(2, 9)}`
}

function generateWorkflowId() {
  return `wf-${Math.random().toString(36).slice(2, 8)}`
}

function formatRate(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function randomMetricSet(seed: number): ReportMetric[] {
  const base = (value: number, precision = 3) => (value + seed * 0.003).toFixed(precision)
  const annual = 0.12 + seed * 0.005
  const drawdown = -(0.04 + seed * 0.002)
  const turnover = 0.48 + seed * 0.015
  return [
    { label: 'IC均值', value: base(0.072), trend: 'up' },
    { label: 'RankIC', value: base(0.096), trend: 'up' },
    { label: '年化收益', value: formatRate(annual), trend: 'up' },
    { label: '最大回撤', value: formatRate(drawdown), trend: 'down' },
    { label: '夏普比率', value: base(1.61, 2), trend: 'up' },
    { label: '换手率', value: base(turnover, 2), trend: 'down' },
  ]
}

function randomSeries(seed: number) {
  const values = [1]
  for (let i = 1; i < 14; i += 1) {
    const drift = 0.015 + seed * 0.0008
    const noise = (Math.sin(i + seed) * 0.02 + 0.01) / 2
    values.push(Number((values[i - 1] * (1 + drift + noise)).toFixed(4)))
  }
  return values
}

function randomLayer(seed: number) {
  return [
    { layer: 'Q1', value: Number((-0.02 - seed * 0.001).toFixed(3)) },
    { layer: 'Q2', value: Number((0.01 + seed * 0.001).toFixed(3)) },
    { layer: 'Q3', value: Number((0.04 + seed * 0.001).toFixed(3)) },
    { layer: 'Q4', value: Number((0.08 + seed * 0.001).toFixed(3)) },
    { layer: 'Q5', value: Number((0.14 + seed * 0.001).toFixed(3)) },
  ]
}

function createInitialState(): PersistedState {
  if (typeof window !== 'undefined') {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw) {
      try {
        return JSON.parse(raw) as PersistedState
      } catch {
        // ignore damaged local cache
      }
    }
  }
  return {
    workflows: workflowList,
    runs: runRecords,
    graphs: seededGraphs,
    reports: seededReports,
  }
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const initial = createInitialState()
  const [workflows, setWorkflows] = useState<Workflow[]>(initial.workflows)
  const [runs, setRuns] = useState<RunRecord[]>(initial.runs)
  const [graphs, setGraphs] = useState<Record<string, WorkflowGraph>>(initial.graphs)
  const [reports, setReports] = useState<Record<string, ReportSnapshot>>(initial.reports)
  const [notice, setNotice] = useState<string | null>(null)

  const persist = (next: PersistedState) => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    }
  }

  const updateNotice = (text: string) => {
    setNotice(text)
    window.setTimeout(() => setNotice(null), 2400)
  }

  useEffect(() => {
    persist({ workflows, runs, graphs, reports })
  }, [workflows, runs, graphs, reports])

  const createWorkflow: WorkspaceStore['createWorkflow'] = (payload) => {
    const id = generateWorkflowId()
    const createdAt = nowText()
    const workflow: Workflow = {
      id,
      name: payload.name.trim(),
      category: payload.category.trim(),
      tags: payload.tags,
      status: 'draft',
      updatedAt: createdAt,
      description: payload.description,
      sourceTemplateId: payload.sourceTemplateId,
    }
    const nextWorkflows = [workflow, ...workflows]
    const nextGraphs = {
      ...graphs,
      [id]: cloneGraph(payload.graph),
    }
    setWorkflows(nextWorkflows)
    setGraphs(nextGraphs)
    updateNotice(`已创建工作流：${workflow.name}`)
    return id
  }

  const cloneTemplate: WorkspaceStore['cloneTemplate'] = (templateId) => {
    const source = templates.find((item) => item.id === templateId)
    if (!source) return null
    const nextId = createWorkflow({
      name: `${source.name}-副本`,
      category: source.category,
      tags: source.tags,
      description: source.description,
      graph: source.graph,
      sourceTemplateId: source.id,
    })
    return nextId
  }

  const saveWorkflowGraph: WorkspaceStore['saveWorkflowGraph'] = (workflowId, graph) => {
    const nextGraphs = {
      ...graphs,
      [workflowId]: cloneGraph(graph),
    }
    setGraphs(nextGraphs)
  }

  const saveWorkflowDraft: WorkspaceStore['saveWorkflowDraft'] = (workflowId) => {
    const nextWorkflows: Workflow[] = workflows.map((item) =>
      item.id === workflowId ? { ...item, status: 'draft', updatedAt: nowText() } : item,
    )
    setWorkflows(nextWorkflows)
    const workflowName = workflows.find((item) => item.id === workflowId)?.name ?? workflowId
    updateNotice(`已保存草稿：${workflowName}`)
  }

  const updateRunStatus = (runId: string, status: RunStatus, message: string, duration?: string) => {
    setRuns((prev) => {
      const nextRuns = prev.map((run) =>
        run.id === runId
          ? {
              ...run,
              status,
              message,
              duration: duration ?? run.duration,
            }
          : run,
      )
      return nextRuns
    })
  }

  const runWorkflow: WorkspaceStore['runWorkflow'] = (workflowId) => {
    const workflow = workflows.find((item) => item.id === workflowId)
    if (!workflow) return

    const startedAt = Date.now()
    const runId = generateRunId()
    const createdAt = nowText()
    const queuedRun: RunRecord = {
      id: runId,
      workflowId,
      workflowName: workflow.name,
      status: 'queued',
      duration: '00m 00s',
      createdAt,
      message: '任务已进入队列，等待调度。',
    }
    const nextRuns = [queuedRun, ...runs]
    const nextWorkflows: Workflow[] = workflows.map((item) =>
      item.id === workflowId ? { ...item, status: 'running', lastRun: createdAt, updatedAt: createdAt } : item,
    )
    setRuns(nextRuns)
    setWorkflows(nextWorkflows)
    updateNotice(`已启动运行：${workflow.name}`)

    window.setTimeout(() => {
      updateRunStatus(runId, 'running', '正在执行节点链路与参数校验...')
    }, 650)

    window.setTimeout(() => {
      const duration = createDuration(startedAt)
      updateRunStatus(runId, 'success', '执行完成，报告已更新。', duration)
      const seed = Math.max(1, workflow.name.length % 7)
      const report: ReportSnapshot = {
        workflowId,
        workflowName: workflow.name,
        metrics: randomMetricSet(seed),
        equitySeries: randomSeries(seed),
        layerReturn: randomLayer(seed),
        updatedAt: nowText(),
      }
      setReports((prev) => {
        const nextReports = {
          ...prev,
          [workflowId]: report,
        }
        return nextReports
      })
      setWorkflows((prev) => {
        const finalWorkflows: Workflow[] = prev.map((item) =>
          item.id === workflowId ? { ...item, status: 'published', lastRun: nowText() } : item,
        )
        return finalWorkflows
      })
      updateNotice(`运行完成：${workflow.name}`)
    }, 2800)
  }

  const value: WorkspaceStore = {
    workflows,
    templates,
    runs,
    nodeLibrary,
    reports,
    getGraphByWorkflowId: (workflowId) => graphs[workflowId],
    createWorkflow,
    cloneTemplate,
    saveWorkflowGraph,
    saveWorkflowDraft,
    runWorkflow,
    getReportByWorkflowId: (workflowId) => reports[workflowId],
    notice,
  }

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
