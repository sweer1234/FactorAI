/* eslint-disable react-refresh/only-export-components */
import { createContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  cloneTemplate as apiCloneTemplate,
  createWorkflow as apiCreateWorkflow,
  fetchBootstrap,
  fetchReport,
  fetchRunLogs,
  fetchRunNodeStates,
  fetchRuns,
  fetchTemplates,
  fetchWorkflows,
  runWorkflow as apiRunWorkflow,
  saveWorkflowDraft as apiSaveWorkflowDraft,
  saveWorkflowGraph as apiSaveWorkflowGraph,
} from '../api/client'
import {
  nodeLibrary as fallbackNodeLibrary,
  runRecords as fallbackRuns,
  templates as fallbackTemplates,
  workflowList,
} from '../data/mock'
import type {
  NodeDefinition,
  NodeState,
  ReportSnapshot,
  RunLog,
  RunRecord,
  Template,
  Workflow,
  WorkflowGraph,
} from '../types'

export interface WorkspaceStore {
  workflows: Workflow[]
  templates: Template[]
  runs: RunRecord[]
  nodeLibrary: NodeDefinition[]
  reports: Record<string, ReportSnapshot>
  runLogsByRunId: Record<string, RunLog[]>
  nodeStatesByRunId: Record<string, NodeState[]>
  loading: boolean
  backendOnline: boolean
  getGraphByWorkflowId: (workflowId: string) => WorkflowGraph | undefined
  getLatestRunByWorkflowId: (workflowId: string) => RunRecord | undefined
  getRunLogs: (runId?: string) => RunLog[]
  getNodeStates: (runId?: string) => NodeState[]
  createWorkflow: (payload: {
    name: string
    category: string
    tags: string[]
    description?: string
    graph?: WorkflowGraph
  }) => Promise<string>
  cloneTemplate: (templateId: string) => Promise<string | null>
  saveWorkflowGraph: (workflowId: string, graph: WorkflowGraph) => Promise<void>
  saveWorkflowDraft: (workflowId: string) => Promise<void>
  runWorkflow: (workflowId: string) => Promise<void>
  getReportByWorkflowId: (workflowId: string) => ReportSnapshot | undefined
  refreshExecutionByWorkflowId: (workflowId: string) => Promise<void>
  notice: string | null
}

export const WorkspaceContext = createContext<WorkspaceStore | null>(null)

function withFallbackGraph(workflows: Workflow[]) {
  return workflows.map((item) => ({ ...item, graph: item.graph ?? { nodes: [], edges: [] } }))
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workflows, setWorkflows] = useState<Workflow[]>(withFallbackGraph(workflowList))
  const [templates, setTemplates] = useState<Template[]>(fallbackTemplates)
  const [runs, setRuns] = useState<RunRecord[]>(fallbackRuns)
  const [nodeLibrary, setNodeLibrary] = useState<NodeDefinition[]>(fallbackNodeLibrary)
  const [reports, setReports] = useState<Record<string, ReportSnapshot>>({})
  const [runLogsByRunId, setRunLogsByRunId] = useState<Record<string, RunLog[]>>({})
  const [nodeStatesByRunId, setNodeStatesByRunId] = useState<Record<string, NodeState[]>>({})
  const [notice, setNotice] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [backendOnline, setBackendOnline] = useState(false)

  const updateNotice = (text: string) => {
    setNotice(text)
    window.setTimeout(() => setNotice(null), 2600)
  }

  const getLatestRunByWorkflowId = (workflowId: string) => runs.find((item) => item.workflowId === workflowId)

  const refreshWorkflows = async () => {
    const list = await fetchWorkflows()
    setWorkflows(withFallbackGraph(list))
  }

  const refreshRuns = async () => {
    const list = await fetchRuns()
    setRuns(list)
    return list
  }

  const refreshTemplates = async () => {
    const list = await fetchTemplates({ official: true })
    setTemplates(list)
  }

  const refreshReport = async (workflowId: string) => {
    const report = await fetchReport(workflowId)
    if (!report) return
    setReports((prev) => ({ ...prev, [workflowId]: report }))
  }

  const refreshRunDetails = async (runId: string) => {
    const [logs, nodeStates] = await Promise.all([fetchRunLogs(runId), fetchRunNodeStates(runId)])
    setRunLogsByRunId((prev) => ({ ...prev, [runId]: logs }))
    setNodeStatesByRunId((prev) => ({ ...prev, [runId]: nodeStates }))
  }

  const refreshExecutionByWorkflowId = async (workflowId: string) => {
    const latestRuns = await refreshRuns()
    const latest = latestRuns.find((item) => item.workflowId === workflowId)
    if (latest) {
      await refreshRunDetails(latest.id)
    }
  }

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const payload = await fetchBootstrap()
        setWorkflows(withFallbackGraph(payload.workflows))
        setTemplates(payload.templates)
        setRuns(payload.runs)
        setNodeLibrary(payload.nodeLibrary)
        setBackendOnline(true)
      } catch {
        setBackendOnline(false)
      } finally {
        setLoading(false)
      }
    }
    bootstrap()
  }, [])

  const createWorkflow: WorkspaceStore['createWorkflow'] = async (payload) => {
    if (!backendOnline) {
      const localId = `wf-local-${Date.now()}`
      setWorkflows((prev) => [
        {
          id: localId,
          name: payload.name,
          category: payload.category,
          tags: payload.tags,
          status: 'draft',
          updatedAt: new Date().toISOString(),
          description: payload.description,
          graph: payload.graph ?? { nodes: [], edges: [] },
        },
        ...prev,
      ])
      updateNotice('本地模式：已创建工作流')
      return localId
    }

    const created = await apiCreateWorkflow(payload)
    setWorkflows((prev) => [created, ...prev])
    updateNotice(`已创建工作流：${created.name}`)
    return created.id
  }

  const cloneTemplate: WorkspaceStore['cloneTemplate'] = async (templateId) => {
    if (!backendOnline) {
      const template = templates.find((item) => item.id === templateId)
      if (!template) return null
      const id = await createWorkflow({
        name: `${template.name}-副本`,
        category: template.category,
        tags: template.tags,
        description: template.description,
        graph: template.graph,
      })
      return id
    }

    const created = await apiCloneTemplate(templateId)
    setWorkflows((prev) => [created, ...prev])
    updateNotice(`模板复制完成：${created.name}`)
    return created.id
  }

  const saveWorkflowGraph: WorkspaceStore['saveWorkflowGraph'] = async (workflowId, graph) => {
    setWorkflows((prev) => prev.map((item) => (item.id === workflowId ? { ...item, graph } : item)))
    if (!backendOnline) return
    try {
      const updated = await apiSaveWorkflowGraph(workflowId, graph)
      setWorkflows((prev) => prev.map((item) => (item.id === workflowId ? updated : item)))
    } catch {
      updateNotice('保存失败：后端不可达')
    }
  }

  const saveWorkflowDraft: WorkspaceStore['saveWorkflowDraft'] = async (workflowId) => {
    if (!backendOnline) {
      setWorkflows((prev) =>
        prev.map((item) =>
          item.id === workflowId ? { ...item, status: 'draft', updatedAt: new Date().toISOString() } : item,
        ),
      )
      updateNotice('本地模式：草稿已保存')
      return
    }
    const updated = await apiSaveWorkflowDraft(workflowId)
    setWorkflows((prev) => prev.map((item) => (item.id === workflowId ? updated : item)))
    updateNotice(`已保存草稿：${updated.name}`)
  }

  const runWorkflow: WorkspaceStore['runWorkflow'] = async (workflowId) => {
    const workflow = workflows.find((item) => item.id === workflowId)
    if (!workflow) return

    if (!backendOnline) {
      updateNotice('本地模式：已模拟运行')
      return
    }
    const run = await apiRunWorkflow(workflowId)
    setRuns((prev) => [run, ...prev])
    updateNotice(`已启动运行：${workflow.name}`)

    let round = 0
    const poll = async () => {
      round += 1
      const [latestRuns] = await Promise.all([
        refreshRuns(),
        refreshWorkflows(),
        refreshTemplates(),
        refreshReport(workflowId),
      ])
      const latest = latestRuns.find((item) => item.workflowId === workflowId) ?? run
      await refreshRunDetails(latest.id)
      if (round < 20 && latest.status !== 'success' && latest.status !== 'failed') {
        window.setTimeout(poll, 1200)
      }
    }
    window.setTimeout(poll, 900)
  }

  const getGraphByWorkflowId = (workflowId: string) =>
    workflows.find((item) => item.id === workflowId)?.graph ?? { nodes: [], edges: [] }

  const getReportByWorkflowId = (workflowId: string) => reports[workflowId]

  const getRunLogs = (runId?: string) => {
    if (!runId) return []
    return runLogsByRunId[runId] ?? []
  }

  const getNodeStates = (runId?: string) => {
    if (!runId) return []
    return nodeStatesByRunId[runId] ?? []
  }

  const value = useMemo<WorkspaceStore>(
    () => ({
      workflows,
      templates,
      runs,
      nodeLibrary,
      reports,
      runLogsByRunId,
      nodeStatesByRunId,
      loading,
      backendOnline,
      getGraphByWorkflowId,
      getLatestRunByWorkflowId,
      getRunLogs,
      getNodeStates,
      createWorkflow,
      cloneTemplate,
      saveWorkflowGraph,
      saveWorkflowDraft,
      runWorkflow,
      getReportByWorkflowId,
      refreshExecutionByWorkflowId,
      notice,
    }),
    [workflows, templates, runs, nodeLibrary, reports, runLogsByRunId, nodeStatesByRunId, loading, backendOnline, notice],
  )

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
