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
import type { GraphNode } from '../types'

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

function statusText(index: number) {
  if (index === 0) return '已完成'
  if (index === 1) return '运行中'
  return '待运行'
}

export function EditorPage() {
  const { workflowId = '' } = useParams()
  const { workflows, nodeLibrary, getGraphByWorkflowId, saveWorkflowGraph, runWorkflow } = useWorkspace()
  const [keyword, setKeyword] = useState('')
  const workflow = workflows.find((item) => item.id === workflowId)
  const graph = workflow ? getGraphByWorkflowId(workflow.id) : undefined

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(toReactNodes(graph?.nodes ?? []))
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>((graph?.edges ?? []).map((edge) => ({ ...edge })))
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const nodeSeqRef = useRef(1000)
  const saveDebounceRef = useRef<number | null>(null)

  useEffect(() => {
    const seedNodes = toReactNodes(graph?.nodes ?? [])
    const seedEdges = (graph?.edges ?? []).map((edge) => ({ ...edge }))
    setNodes(seedNodes)
    setEdges(seedEdges)
  }, [workflowId])

  const currentSelectedNodeId = useMemo(() => {
    if (selectedNodeId && nodes.some((item) => item.id === selectedNodeId)) {
      return selectedNodeId
    }
    return nodes[0]?.id ?? null
  }, [selectedNodeId, nodes])

  useEffect(() => {
    if (!workflow) return
    if (saveDebounceRef.current) {
      window.clearTimeout(saveDebounceRef.current)
    }
    saveDebounceRef.current = window.setTimeout(() => {
      void saveWorkflowGraph(workflow.id, {
        nodes: toGraphNodes(nodes),
        edges: edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          animated: Boolean(edge.animated),
        })),
      })
    }, 320)
  }, [nodes, edges])

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
      position: { x: 260 + (nodes.length % 3) * 240, y: 280 + (nodes.length % 2) * 160 },
      style: {
        ...styleByVariant(styleVariant),
        borderRadius: 10,
      },
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
        <div className="panel-header">
          <h3>节点库</h3>
          <input
            className="search-input"
            placeholder="搜索节点"
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
                    <button type="button" onClick={() => addNodeFromLibrary(item.name)}>
                      {item.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {Object.keys(groupedLibrary).length === 0 ? <p className="muted">未搜索到匹配节点。</p> : null}
        </div>
      </aside>

      <div className="editor-canvas panel">
        <div className="panel-header">
          <h3>{workflow.name}</h3>
          <div className="header-actions">
            <span className="tag">节点 {nodes.length}</span>
            <span className="tag">连线 {edges.length}</span>
            <button type="button" className="primary ghost" onClick={removeSelectedNode}>
              删除选中节点
            </button>
            <button type="button" className="primary" onClick={() => void runWorkflow(workflow.id)}>
              快速运行
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
          <h3>节点详情</h3>
          <span className="tag">{currentSelectedNodeId ? `节点 ${currentSelectedNodeId}` : '未选择'}</span>
        </div>
        <article className="node-detail">
          <h4>{selectedDefinition.name}</h4>
          <p>{selectedDefinition.description}</p>

          <div className="detail-block">
            <h5>输入字段</h5>
            <ul>
              {selectedDefinition.inputs.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="detail-block">
            <h5>输出字段</h5>
            <ul>
              {selectedDefinition.outputs.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div className="detail-block">
            <h5>核心参数</h5>
            <ul>
              {selectedDefinition.params.map((param) => (
                <li key={param.key}>
                  {param.key} ({param.type}) = {String(param.defaultValue ?? '-')}
                </li>
              ))}
            </ul>
          </div>
        </article>

        <div className="timeline">
          <h5>运行阶段</h5>
          <ol>
            {['数据准备', '特征处理', '模型训练', '因子生成', '回测评估'].map((step, idx) => (
              <li key={step}>
                <span>{step}</span>
                <em>{statusText(idx)}</em>
              </li>
            ))}
          </ol>
        </div>
      </aside>
    </section>
  )
}
