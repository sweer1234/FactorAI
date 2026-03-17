import { useEffect, useMemo, useRef, useState } from 'react'
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
import type { GraphNode, NodeState } from '../types'

type EditorTab = 'library' | 'logs' | 'current'

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

function toReactNodes(nodes: GraphNode[]): Node[] {
  return nodes.map((item) => ({
    id: item.id,
    position: { ...item.position },
    data: { label: item.label, styleVariant: item.styleVariant },
    style: {
      ...styleByVariant(item.styleVariant),
      borderRadius: 10,
      minWidth: 148,
    },
  }))
}

function toGraphNodes(nodes: Node[]): GraphNode[] {
  return nodes.map((item) => ({
    id: item.id,
    label: String(item.data?.label ?? item.id),
    position: { x: item.position.x, y: item.position.y },
    styleVariant: (item.data?.styleVariant as GraphNode['styleVariant']) ?? 'default',
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
  } = useWorkspace()

  const [activeTab, setActiveTab] = useState<EditorTab>('library')
  const [keyword, setKeyword] = useState('')
  const workflow = workflows.find((item) => item.id === workflowId)
  const graph = workflow ? getGraphByWorkflowId(workflow.id) : undefined
  const seedNodes = useMemo(() => toReactNodes(graph?.nodes ?? []), [graph?.nodes])
  const seedEdges = useMemo(() => (graph?.edges ?? []).map((edge) => ({ ...edge })), [graph?.edges])

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(seedNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(seedEdges)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const nodeSeqRef = useRef(2000)
  const saveDebounceRef = useRef<number | null>(null)
  const refreshExecutionRef = useRef(refreshExecutionByWorkflowId)
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
    const nodeName = nodes.find((item) => item.id === currentSelectedNodeId)?.data?.label
    return nodeLibrary.find((item) => item.name === nodeName) ?? nodeLibrary[0]
  }, [nodes, currentSelectedNodeId, nodeLibrary])

  const latestRun = workflow ? getLatestRunByWorkflowId(workflow.id) : undefined
  const runLogs = getRunLogs(latestRun?.id)
  const nodeStates = getNodeStates(latestRun?.id)
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
    const nextNode: Node = {
      id: nextId,
      data: { label: name, styleVariant },
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
              <button type="button" className="primary ghost mini">
                上传
              </button>
              <input
                className="search-input"
                placeholder="搜索目录"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              />
            </div>
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
                <article key={item.id} className={`editor-log-item ${item.level.toLowerCase()}`}>
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
                    <span>
                      {param.type} / 默认 {String(param.defaultValue ?? '-')}
                    </span>
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
