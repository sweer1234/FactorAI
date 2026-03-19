import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from '@xyflow/react'
import { Link, useParams } from 'react-router-dom'
import { useWorkspace } from '../hooks/useWorkspace'
import type { GraphNode, NodeDefinition, NodeState } from '../types'

type EditorTab = 'library' | 'logs' | 'current'
type FlowNodeData = {
  label: string
  styleVariant?: GraphNode['styleVariant']
  nodeSpecId?: string
  params?: Record<string, string | number | boolean>
  inputs?: string[]
  outputs?: string[]
}

function styleByVariant(variant?: GraphNode['styleVariant']) {
  if (variant === 'data') return { background: '#102d3b', color: '#d2eeff', border: '1px solid #1a6b8f' }
  if (variant === 'feature')
    return { background: '#1f2a1d', color: '#ddf4d1', border: '1px solid #3d8652' }
  if (variant === 'model') return { background: '#2f2224', color: '#ffd9de', border: '1px solid #8c3e4d' }
  if (variant === 'factor') return { background: '#26243f', color: '#dbd9ff', border: '1px solid #5751a9' }
  if (variant === 'backtest')
    return { background: '#312f1f', color: '#fff3c8', border: '1px solid #8f8041' }
  return { background: '#1f2332', color: '#e7eaff', border: '1px solid #5661c6' }
}

function toReactNodes(nodes: GraphNode[], nodeLibrary: NodeDefinition[]): Node<FlowNodeData>[] {
  const specMap = new Map(nodeLibrary.map((item) => [item.id, item]))
  return nodes.map((item) => ({
    id: item.id,
    position: { ...item.position },
    data: {
      label: item.label,
      styleVariant: item.styleVariant,
      nodeSpecId: item.nodeSpecId,
      params: item.params ?? {},
      inputs: specMap.get(item.nodeSpecId ?? '')?.inputs ?? [],
      outputs: specMap.get(item.nodeSpecId ?? '')?.outputs ?? [],
    },
    style: {
      ...styleByVariant(item.styleVariant),
      borderRadius: 10,
      minWidth: 148,
    },
  }))
}

function toGraphNodes(nodes: Node<FlowNodeData>[]): GraphNode[] {
  return nodes.map((item) => ({
    id: item.id,
    label: String(item.data?.label ?? item.id),
    position: { x: item.position.x, y: item.position.y },
    styleVariant: (item.data?.styleVariant as GraphNode['styleVariant']) ?? 'default',
    nodeSpecId: item.data?.nodeSpecId,
    params: item.data?.params ?? {},
  }))
}

function nodeStatusText(status: NodeState['status'] | undefined) {
  if (status === 'running') return '运行中'
  if (status === 'success') return '完成'
  if (status === 'failed') return '失败'
  if (status === 'queued') return '排队'
  return '未运行'
}

export function EditorPage() {
  const { workflowId = '' } = useParams()
  const {
    workflows,
    nodeLibrary,
    getGraphByWorkflowId,
    saveWorkflowGraph,
    runWorkflow,
    getLatestRunByWorkflowId,
    getRunLogs,
    getNodeStates,
    refreshExecutionByWorkflowId,
    getArtifactsByWorkflowId,
    uploadArtifactForWorkflow,
    applyContractFixes,
    rollbackContractFixes,
  } = useWorkspace()

  const [activeTab, setActiveTab] = useState<EditorTab>('library')
  const [keyword, setKeyword] = useState('')
  const workflow = workflows.find((item) => item.id === workflowId)
  const graph = workflow ? getGraphByWorkflowId(workflow.id) : undefined
  const seedNodes = useMemo(() => toReactNodes(graph?.nodes ?? [], nodeLibrary), [graph?.nodes, nodeLibrary])
  const seedEdges = useMemo(() => (graph?.edges ?? []).map((edge) => ({ ...edge })), [graph?.edges])

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<FlowNodeData>>(seedNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(seedEdges)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const nodeSeqRef = useRef(2000)
  const saveDebounceRef = useRef<number | null>(null)
  const refreshExecutionRef = useRef(refreshExecutionByWorkflowId)
  const fileRef = useRef<HTMLInputElement | null>(null)
  const [editorNotice, setEditorNotice] = useState<string | null>(null)
  const [applyingFixes, setApplyingFixes] = useState(false)
  const [rollingBackFixes, setRollingBackFixes] = useState(false)
  const activeWorkflowId = workflow?.id

  useEffect(() => {
    refreshExecutionRef.current = refreshExecutionByWorkflowId
  }, [refreshExecutionByWorkflowId])

  useEffect(() => {
    setNodes(seedNodes)
    setEdges(seedEdges)
  }, [workflowId, seedNodes, seedEdges, setNodes, setEdges])

  useEffect(() => {
    if (!activeWorkflowId) return
    if (saveDebounceRef.current) {
      window.clearTimeout(saveDebounceRef.current)
    }
    saveDebounceRef.current = window.setTimeout(() => {
      void saveWorkflowGraph(activeWorkflowId, {
        nodes: toGraphNodes(nodes),
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          animated: Boolean(edge.animated),
        })),
      })
    }, 320)
  }, [nodes, edges, saveWorkflowGraph, activeWorkflowId])

  useEffect(() => {
    if (!workflow?.id) return
    void refreshExecutionRef.current(workflow.id)
  }, [workflow?.id])

  const currentSelectedNodeId = useMemo(() => {
    if (selectedNodeId && nodes.some((item) => item.id === selectedNodeId)) {
      return selectedNodeId
    }
    return nodes[0]?.id ?? null
  }, [selectedNodeId, nodes])

  const groupedLibrary = useMemo(() => {
    const filtered = nodeLibrary.filter((item) => {
      if (!keyword.trim()) return true
      const key = keyword.trim().toLowerCase()
      return (
        item.name.toLowerCase().includes(key) ||
        item.category.toLowerCase().includes(key) ||
        item.description.toLowerCase().includes(key)
      )
    })
    return filtered.reduce<Record<string, typeof nodeLibrary>>((acc, item) => {
      if (!acc[item.category]) acc[item.category] = []
      acc[item.category].push(item)
      return acc
    }, {})
  }, [nodeLibrary, keyword])

  const selectedDefinition = useMemo(() => {
    const node = nodes.find((item) => item.id === currentSelectedNodeId)
    const byId = nodeLibrary.find((item) => item.id === node?.data?.nodeSpecId)
    if (byId) return byId
    const nodeName = node?.data?.label
    return nodeLibrary.find((item) => item.name === nodeName) ?? nodeLibrary[0]
  }, [nodes, currentSelectedNodeId, nodeLibrary])

  const latestRun = workflow ? getLatestRunByWorkflowId(workflow.id) : undefined
  const runLogs = getRunLogs(latestRun?.id)
  const nodeStates = getNodeStates(latestRun?.id)
  const artifacts = workflow ? getArtifactsByWorkflowId(workflow.id) : []
  const nodeStateMap = new Map(nodeStates.map((item) => [item.nodeId, item]))

  const currentNodeList = [...nodes].sort((a, b) => a.position.x - b.position.x).map((node) => {
    const state = nodeStateMap.get(node.id)
    return {
      id: node.id,
      name: String(node.data?.label ?? node.id),
      status: state?.status,
    }
  })

  const onConnect = (params: Connection) => {
    const source = nodes.find((item) => item.id === params.source)
    const target = nodes.find((item) => item.id === params.target)
    const sourceOutputs = source?.data?.outputs ?? []
    const targetInputs = target?.data?.inputs ?? []
    if (
      source &&
      target &&
      sourceOutputs.length > 0 &&
      targetInputs.length > 0 &&
      sourceOutputs.every((out) => !targetInputs.includes(out))
    ) {
      setEditorNotice(
        `连线失败：${String(source.data.label)} 输出[${sourceOutputs.join(', ')}] 与 ${String(target.data.label)} 输入[${targetInputs.join(', ')}] 不匹配`,
      )
      return
    }
    setEdges((eds) => addEdge({ ...params, animated: true }, eds))
  }

  const addNodeFromLibrary = (name: string) => {
    const definition = nodeLibrary.find((item) => item.name === name)
    nodeSeqRef.current += 1
    const nextId = `n${nodeSeqRef.current}`
    const styleVariant = definition?.category.startsWith('01')
      ? 'data'
      : definition?.category.startsWith('02')
        ? 'feature'
        : definition?.category.startsWith('03')
          ? 'model'
          : definition?.category.startsWith('04')
            ? 'factor'
            : definition?.category.startsWith('05')
              ? 'backtest'
              : 'default'
    const nextNode: Node<FlowNodeData> = {
      id: nextId,
      data: {
        label: name,
        styleVariant,
        nodeSpecId: definition?.id,
        params: Object.fromEntries((definition?.params ?? []).map((item) => [item.key, item.defaultValue ?? ''])),
        inputs: definition?.inputs ?? [],
        outputs: definition?.outputs ?? [],
      },
      position: { x: 280 + (nodes.length % 3) * 210, y: 260 + (nodes.length % 2) * 160 },
      style: { ...styleByVariant(styleVariant), borderRadius: 10, minWidth: 148 },
    }
    setNodes((prev) => [...prev, nextNode])
    setSelectedNodeId(nextId)
  }

  const removeSelectedNode = () => {
    if (!selectedNodeId) return
    setNodes((prev) => prev.filter((item) => item.id !== selectedNodeId))
    setEdges((prev) => prev.filter((item) => item.source !== selectedNodeId && item.target !== selectedNodeId))
    setSelectedNodeId(null)
  }

  const selectedNode = nodes.find((item) => item.id === currentSelectedNodeId)
  const selectedParams = selectedNode?.data?.params ?? {}
  const selectedNodeSpecId = selectedNode?.data?.nodeSpecId

  const updateParam = (key: string, value: string | number | boolean) => {
    if (!currentSelectedNodeId) return
    setNodes((prev) =>
      prev.map((node) => {
        if (node.id !== currentSelectedNodeId) return node
        const current = node.data?.params ?? {}
        return {
          ...node,
          data: {
            ...node.data,
            params: { ...current, [key]: value },
          },
        }
      }),
    )
  }

  const onUploadClicked = () => fileRef.current?.click()

  const onAutoApplyFixes = async () => {
    if (!workflow) return
    setApplyingFixes(true)
    try {
      const result = await applyContractFixes(workflow.id)
      if (!result) {
        setEditorNotice('自动修复未执行')
        return
      }
      const nextGraph = result.workflow.graph
      setNodes(toReactNodes(nextGraph.nodes ?? [], nodeLibrary))
      setEdges((nextGraph.edges ?? []).map((edge) => ({ ...edge })))
      const appliedCount = result.appliedActions.filter((item) => item.status === 'applied').length
      setEditorNotice(
        `自动修复已应用 ${appliedCount} 条，当前错误 ${result.compile.errors.length} 条，警告 ${result.compile.warnings.length} 条`,
      )
    } catch {
      setEditorNotice('自动修复失败，请稍后重试')
    } finally {
      setApplyingFixes(false)
    }
  }

  const onRollbackFixes = async () => {
    if (!workflow) return
    setRollingBackFixes(true)
    try {
      const result = await rollbackContractFixes(workflow.id)
      if (!result) {
        setEditorNotice('回滚未执行')
        return
      }
      const nextGraph = result.workflow.graph
      setNodes(toReactNodes(nextGraph.nodes ?? [], nodeLibrary))
      setEdges((nextGraph.edges ?? []).map((edge) => ({ ...edge })))
      setEditorNotice(
        `已回滚修复版本（${result.restoredRevisionId.slice(-6)}），当前错误 ${result.compile.errors.length} 条，警告 ${result.compile.warnings.length} 条`,
      )
    } catch {
      setEditorNotice('回滚失败：暂无可回滚版本')
    } finally {
      setRollingBackFixes(false)
    }
  }

  const bindArtifactToSelected = (artifactId: string, fileName: string) => {
    if (!selectedNodeSpecId) {
      setEditorNotice('请先选择一个节点')
      return
    }
    if (selectedNodeSpecId === 'basic.model_upload') {
      updateParam('artifactId', artifactId)
      updateParam('path', fileName)
      setEditorNotice(`已绑定模型制品：${fileName}`)
      return
    }
    if (selectedNodeSpecId === 'offline.alphagen_upload') {
      updateParam('artifactId', artifactId)
      updateParam('artifact_path', fileName)
      setEditorNotice(`已绑定 AlphaGen 制品：${fileName}`)
      return
    }
    setEditorNotice('当前节点非上传类节点，未自动绑定')
  }

  const onUploadSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file || !workflow) return
    try {
      const artifact = await uploadArtifactForWorkflow(workflow.id, file, 'node-input')
      if (artifact) {
        bindArtifactToSelected(artifact.id, artifact.fileName)
      }
      setEditorNotice(`上传成功：${file.name}`)
    } catch {
      setEditorNotice(`上传失败：${file.name}`)
    } finally {
      event.target.value = ''
    }
  }

  if (!workflow) {
    return (
      <section className="panel empty-state">
        <h3>工作流不存在</h3>
        <p>请返回工作流列表重新选择。</p>
        <Link className="primary" to="/workflows">
          返回工作流列表
        </Link>
      </section>
    )
  }

  return (
    <section className="editor-layout">
      <aside className="editor-left panel">
        <div className="editor-tabs">
          <button
            type="button"
            className={`editor-tab ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
          >
            节点库
          </button>
          <button
            type="button"
            className={`editor-tab ${activeTab === 'logs' ? 'active' : ''}`}
            onClick={() => setActiveTab('logs')}
          >
            日志
          </button>
          <button
            type="button"
            className={`editor-tab ${activeTab === 'current' ? 'active' : ''}`}
            onClick={() => setActiveTab('current')}
          >
            当前节点
          </button>
        </div>

        {activeTab === 'library' ? (
          <>
            <div className="panel-header">
              <button type="button" className="primary ghost mini" onClick={onUploadClicked}>
                上传
              </button>
              <button type="button" className="primary ghost mini" onClick={() => void onAutoApplyFixes()} disabled={applyingFixes}>
                {applyingFixes ? '修复中…' : '自动修复契约'}
              </button>
              <button
                type="button"
                className="primary ghost mini"
                onClick={() => void onRollbackFixes()}
                disabled={rollingBackFixes}
              >
                {rollingBackFixes ? '回滚中…' : '回滚修复'}
              </button>
              <input ref={fileRef} type="file" style={{ display: 'none' }} onChange={onUploadSelected} />
              <input
                className="search-input"
                placeholder="搜索目录"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              />
            </div>
            {editorNotice ? <p className="muted">{editorNotice}</p> : null}
            <div className="tree-list">
              {Object.entries(groupedLibrary).map(([category, list]) => (
                <div key={category} className="tree-group">
                  <h4>
                    {category} <span>{list.length}</span>
                  </h4>
                  <ul>
                    {list.map((item) => (
                      <li key={item.id}>
                        <button
                          type="button"
                          className={selectedDefinition?.id === item.id ? 'active' : ''}
                          onClick={() => addNodeFromLibrary(item.name)}
                        >
                          {item.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              {Object.keys(groupedLibrary).length === 0 ? <p className="muted">未搜索到匹配节点。</p> : null}
            </div>
            <div className="panel-header">
              <h3>已上传文件</h3>
              <span className="tag">{artifacts.length}</span>
            </div>
            <div className="tree-list">
              {artifacts.slice(0, 6).map((item) => (
                <div key={item.id} className="tree-group">
                  <h4>{item.fileName}</h4>
                  <p className="muted">
                    {item.kind}
                    {item.version ? ` v${item.version}` : ''}
                    {item.isActive ? ' · active' : ''}
                    {' · '}
                    {(item.fileSize / 1024).toFixed(1)} KB
                  </p>
                  <button type="button" className="primary ghost mini" onClick={() => bindArtifactToSelected(item.id, item.fileName)}>
                    绑定到当前节点
                  </button>
                </div>
              ))}
              {artifacts.length === 0 ? <p className="muted">暂无上传文件</p> : null}
            </div>
          </>
        ) : null}

        {activeTab === 'logs' ? (
          <div className="editor-log-list">
            <div className="panel-header">
              <h3>运行日志</h3>
              <span className="tag">{latestRun ? latestRun.status : '无任务'}</span>
            </div>
            {runLogs.length === 0 ? (
              <p className="muted">暂无日志，运行工作流后可查看节点执行明细。</p>
            ) : (
              runLogs.map((item) => (
                <article
                  key={item.id}
                  className={`editor-log-item ${item.level.toLowerCase()}`}
                  onClick={() => item.nodeId && setSelectedNodeId(item.nodeId)}
                >
                  <header>
                    <span>{item.level}</span>
                    <time>{item.createdAt}</time>
                  </header>
                  <p>{item.message}</p>
                </article>
              ))
            )}
          </div>
        ) : null}

        {activeTab === 'current' ? (
          <div className="editor-current-list">
            <div className="panel-header">
              <h3>当前节点</h3>
              <span className="tag">{currentNodeList.length}</span>
            </div>
            <ul>
              {currentNodeList.map((item) => (
                <li key={item.id}>
                  <button type="button" onClick={() => setSelectedNodeId(item.id)}>
                    <span className={`dot ${item.status ?? 'idle'}`} />
                    <strong>{item.name}</strong>
                    <em>{nodeStatusText(item.status)}</em>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </aside>

      <div className="editor-canvas panel">
        <div className="panel-header">
          <h3>{workflow.name}</h3>
          <div className="header-actions">
            <span className="tag">节点 {nodes.length}</span>
            <span className="tag">连线 {edges.length}</span>
            <button type="button" className="primary ghost" onClick={removeSelectedNode}>
              删除节点
            </button>
            <button type="button" className="primary" onClick={() => void runWorkflow(workflow.id)}>
              运行工作流
            </button>
          </div>
        </div>
        <div className="flow-wrapper">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            fitView
          >
            <MiniMap />
            <Controls />
            <Background gap={24} />
          </ReactFlow>
        </div>
      </div>

      <aside className="editor-right panel">
        <div className="panel-header">
          <h3>{selectedDefinition?.name ?? '节点详情'}</h3>
          <span className="tag">{currentSelectedNodeId ? `节点 ${currentSelectedNodeId}` : '未选择'}</span>
        </div>

        {selectedDefinition ? (
          <article className="node-doc">
            <section>
              <h4>节点介绍</h4>
              <p>{selectedDefinition.doc?.intro ?? selectedDefinition.description}</p>
            </section>

            <section>
              <h4>工作流示例</h4>
              <p>{selectedDefinition.doc?.workflow_example ?? '推荐将该节点置于因子构建主链路中。'}</p>
            </section>

            <section>
              <h4>核心参数</h4>
              <ul>
                {selectedDefinition.params.map((param) => (
                  <li key={param.key}>
                    <strong>{param.key}</strong>
                    {param.type === 'boolean' ? (
                      <label>
                        <input
                          type="checkbox"
                          checked={Boolean(selectedParams[param.key] ?? param.defaultValue ?? false)}
                          onChange={(event) => updateParam(param.key, event.target.checked)}
                        />
                        <span>启用</span>
                      </label>
                    ) : param.type === 'select' ? (
                      <select
                        value={String(selectedParams[param.key] ?? param.defaultValue ?? '')}
                        onChange={(event) => updateParam(param.key, event.target.value)}
                      >
                        {(param.options ?? []).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : param.key === 'artifactId' ? (
                      <select
                        value={String(selectedParams[param.key] ?? param.defaultValue ?? '')}
                        onChange={(event) => updateParam(param.key, event.target.value)}
                      >
                        <option value="">未绑定</option>
                        {artifacts.map((artifact) => (
                          <option key={artifact.id} value={artifact.id}>
                            {artifact.fileName} ({artifact.id})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="search-input"
                        value={String(selectedParams[param.key] ?? param.defaultValue ?? '')}
                        onChange={(event) =>
                          updateParam(
                            param.key,
                            param.type === 'number' ? Number(event.target.value || 0) : event.target.value,
                          )
                        }
                      />
                    )}
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h4>输入字段</h4>
              <ul>
                {selectedDefinition.inputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>

            <section>
              <h4>输出字段</h4>
              <ul>
                {selectedDefinition.outputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>

            <section>
              <h4>注意事项</h4>
              <ul>
                {(selectedDefinition.doc?.notes ?? ['请确保输入 schema 与节点要求一致。']).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </section>
          </article>
        ) : null}
      </aside>
    </section>
  )
}
