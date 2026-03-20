/* eslint-disable react-refresh/only-export-components */
import { createContext, useEffect, useState, type ReactNode } from 'react'
import {
  batchRunAction as apiBatchRunAction,
  cancelRun as apiCancelRun,
  applyWorkflowContractFixes,
  cloneTemplate as apiCloneTemplate,
  createWorkflow as apiCreateWorkflow,
  fetchArtifacts,
  fetchBootstrap,
  fetchReport,
  fetchWorkflowGraphRevisions,
  fetchRunLogs,
  fetchRunNodeStates,
  fetchRuns,
  fetchTemplates,
  fetchWorkflows,
  publishTemplateFromWorkflow,
  rollbackWorkflowContractFixes,
  retryRun as apiRetryRun,
  retryRunWithStrategy,
  runWorkflow as apiRunWorkflow,
  saveWorkflowDraft as apiSaveWorkflowDraft,
  saveWorkflowGraph as apiSaveWorkflowGraph,
  subscribeTemplate as apiSubscribeTemplate,
  unsubscribeTemplate as apiUnsubscribeTemplate,
  uploadArtifact,
} from '../api/client'
import {
  nodeLibrary as fallbackNodeLibrary,
  runRecords as fallbackRuns,
  templates as fallbackTemplates,
  workflowList,
} from '../data/mock'
import type {
  Artifact,
  ContractFixApplyResult,
  ContractFixRollbackResult,
  GraphRevision,
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
  artifactsByWorkflowId: Record<string, Artifact[]>
  reports: Record<string, ReportSnapshot>
  runLogsByRunId: Record<string, RunLog[]>
  nodeStatesByRunId: Record<string, NodeState[]>
  loading: boolean
  backendOnline: boolean
  getGraphByWorkflowId: (workflowId: string) => WorkflowGraph | undefined
  getArtifactsByWorkflowId: (workflowId: string) => Artifact[]
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
  publishTemplate: (workflowId: string) => Promise<string | null>
  toggleTemplateSubscription: (templateId: string, subscribe: boolean) => Promise<void>
  saveWorkflowGraph: (workflowId: string, graph: WorkflowGraph) => Promise<void>
  saveWorkflowDraft: (workflowId: string) => Promise<void>
  runWorkflow: (workflowId: string) => Promise<void>
  getReportByWorkflowId: (workflowId: string) => ReportSnapshot | undefined
  refreshExecutionByWorkflowId: (workflowId: string) => Promise<void>
  refreshArtifactsByWorkflowId: (workflowId: string) => Promise<void>
  uploadArtifactForWorkflow: (workflowId: string, file: File, kind?: string) => Promise<Artifact | null>
  applyContractFixes: (workflowId: string) => Promise<ContractFixApplyResult | null>
  rollbackContractFixes: (workflowId: string, revisionId?: string) => Promise<ContractFixRollbackResult | null>
  getGraphRevisions: (workflowId: string, source?: string) => Promise<GraphRevision[]>
  cancelRunById: (runId: string) => Promise<void>
  retryRunById: (
    runId: string,
    options?: { strategy?: 'immediate' | 'fixed_backoff'; maxAttempts?: number; backoffSec?: number },
  ) => Promise<void>
  batchRunAction: (payload: {
    action: 'cancel' | 'retry'
    runIds: string[]
    retry?: { strategy?: 'immediate' | 'fixed_backoff'; maxAttempts?: number; backoffSec?: number }
  }) => Promise<{ total: number; success: number; failed: number }>
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
  const [artifactsByWorkflowId, setArtifactsByWorkflowId] = useState<Record<string, Artifact[]>>({})
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
    const list = await fetchTemplates()
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

  const refreshArtifactsByWorkflowId = async (workflowId: string) => {
    if (!backendOnline) return
    const artifacts = await fetchArtifacts({ workflowId })
    setArtifactsByWorkflowId((prev) => ({ ...prev, [workflowId]: artifacts }))
  }

  const refreshExecutionByWorkflowId = async (workflowId: string) => {
    const latestRuns = await refreshRuns()
    const latest = latestRuns.find((item) => item.workflowId === workflowId)
    if (latest) {
      await refreshRunDetails(latest.id)
    }
    await refreshArtifactsByWorkflowId(workflowId)
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

  const publishTemplate: WorkspaceStore['publishTemplate'] = async (workflowId) => {
    if (!backendOnline) {
      updateNotice('后端未连接，无法发布模板')
      return null
    }
    const template = await publishTemplateFromWorkflow(workflowId)
    setTemplates((prev) => [template, ...prev])
    updateNotice(`已发布模板：${template.name}`)
    return template.id
  }

  const toggleTemplateSubscription: WorkspaceStore['toggleTemplateSubscription'] = async (templateId, subscribe) => {
    if (!backendOnline) return
    const updated = subscribe ? await apiSubscribeTemplate(templateId) : await apiUnsubscribeTemplate(templateId)
    setTemplates((prev) => prev.map((item) => (item.id === templateId ? { ...item, ...updated } : item)))
    updateNotice(subscribe ? '已订阅模板' : '已取消订阅')
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
        refreshArtifactsByWorkflowId(workflowId),
      ])
      const latest = latestRuns.find((item) => item.workflowId === workflowId) ?? run
      await refreshRunDetails(latest.id)
      if (round < 20 && latest.status !== 'success' && latest.status !== 'failed' && latest.status !== 'cancelled') {
        window.setTimeout(poll, 1200)
      }
    }
    window.setTimeout(poll, 900)
  }

  const getGraphByWorkflowId = (workflowId: string) =>
    workflows.find((item) => item.id === workflowId)?.graph ?? { nodes: [], edges: [] }
  const getArtifactsByWorkflowId = (workflowId: string) => artifactsByWorkflowId[workflowId] ?? []

  const getReportByWorkflowId = (workflowId: string) => reports[workflowId]

  const getRunLogs = (runId?: string) => {
    if (!runId) return []
    return runLogsByRunId[runId] ?? []
  }

  const getNodeStates = (runId?: string) => {
    if (!runId) return []
    return nodeStatesByRunId[runId] ?? []
  }

  const uploadArtifactForWorkflow = async (workflowId: string, file: File, kind = 'generic') => {
    if (!backendOnline) {
      updateNotice('后端未连接，无法上传')
      return null
    }
    const artifact = await uploadArtifact({ workflowId, file, kind })
    await refreshArtifactsByWorkflowId(workflowId)
    updateNotice(`上传完成：${file.name}`)
    return artifact
  }

  const applyContractFixesForWorkflow: WorkspaceStore['applyContractFixes'] = async (workflowId) => {
    if (!backendOnline) {
      updateNotice('后端未连接，无法自动修复')
      return null
    }
    const result = await applyWorkflowContractFixes(workflowId)
    setWorkflows((prev) => prev.map((item) => (item.id === workflowId ? result.workflow : item)))
    updateNotice(`自动修复完成：应用 ${result.appliedActions.filter((item) => item.status === 'applied').length} 条`)
    return result
  }

  const rollbackContractFixesForWorkflow: WorkspaceStore['rollbackContractFixes'] = async (
    workflowId,
    revisionId,
  ) => {
    if (!backendOnline) {
      updateNotice('后端未连接，无法回滚自动修复')
      return null
    }
    const result = await rollbackWorkflowContractFixes(workflowId, revisionId)
    setWorkflows((prev) => prev.map((item) => (item.id === workflowId ? result.workflow : item)))
    updateNotice('已回滚到自动修复前的图版本')
    return result
  }

  const getGraphRevisions: WorkspaceStore['getGraphRevisions'] = async (workflowId, source) => {
    if (!backendOnline) return []
    return fetchWorkflowGraphRevisions(workflowId, { source, limit: 30 })
  }

  const cancelRunById: WorkspaceStore['cancelRunById'] = async (runId) => {
    if (!backendOnline) return
    const updated = await apiCancelRun(runId)
    setRuns((prev) => prev.map((item) => (item.id === runId ? updated : item)))
    await refreshWorkflows()
    updateNotice(`已请求取消任务：${runId.slice(-8)}`)
  }

  const retryRunById: WorkspaceStore['retryRunById'] = async (runId, options) => {
    if (!backendOnline) return
    const created = options ? await retryRunWithStrategy(runId, options) : await apiRetryRun(runId)
    setRuns((prev) => [created, ...prev])
    await refreshWorkflows()
    updateNotice(`已重试任务：${runId.slice(-8)}`)
  }

  const batchRunAction: WorkspaceStore['batchRunAction'] = async (payload) => {
    if (!backendOnline) return { total: 0, success: 0, failed: 0 }
    const result = await apiBatchRunAction(payload)
    await refreshRuns()
    await refreshWorkflows()
    updateNotice(`批量${payload.action === 'cancel' ? '取消' : '重试'}完成：${result.success}/${result.total}`)
    return { total: result.total, success: result.success, failed: result.failed }
  }

  const value: WorkspaceStore = {
    workflows,
    templates,
    runs,
    nodeLibrary,
    artifactsByWorkflowId,
    reports,
    runLogsByRunId,
    nodeStatesByRunId,
    loading,
    backendOnline,
    getGraphByWorkflowId,
    getArtifactsByWorkflowId,
    getLatestRunByWorkflowId,
    getRunLogs,
    getNodeStates,
    createWorkflow,
    cloneTemplate,
    publishTemplate,
    toggleTemplateSubscription,
    saveWorkflowGraph,
    saveWorkflowDraft,
    runWorkflow,
    getReportByWorkflowId,
    refreshExecutionByWorkflowId,
    refreshArtifactsByWorkflowId,
    uploadArtifactForWorkflow,
    applyContractFixes: applyContractFixesForWorkflow,
    rollbackContractFixes: rollbackContractFixesForWorkflow,
    getGraphRevisions,
    cancelRunById,
    retryRunById,
    batchRunAction,
    notice,
  }

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}
