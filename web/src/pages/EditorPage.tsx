import { useMemo, useState } from 'react'
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
import { nodeLibrary } from '../data/mock'

const initialNodes: Node[] = [
  {
    id: 'n1',
    position: { x: 40, y: 120 },
    data: { label: '行情数据读取' },
    style: { background: '#102d3b', color: '#d2eeff', border: '1px solid #1a6b8f', borderRadius: 10 },
  },
  {
    id: 'n2',
    position: { x: 280, y: 120 },
    data: { label: '特征工程构建' },
    style: { background: '#1f2a1d', color: '#ddf4d1', border: '1px solid #3d8652', borderRadius: 10 },
  },
  {
    id: 'n3',
    position: { x: 520, y: 80 },
    data: { label: 'XGBoost模型' },
    style: { background: '#2f2224', color: '#ffd9de', border: '1px solid #8c3e4d', borderRadius: 10 },
  },
  {
    id: 'n4',
    position: { x: 760, y: 120 },
    data: { label: '自定义因子构建' },
    style: { background: '#26243f', color: '#dbd9ff', border: '1px solid #5751a9', borderRadius: 10 },
  },
  {
    id: 'n5',
    position: { x: 1000, y: 120 },
    data: { label: '期货回测' },
    style: { background: '#312f1f', color: '#fff3c8', border: '1px solid #8f8041', borderRadius: 10 },
  },
]

const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'n1', target: 'n2', animated: true },
  { id: 'e2-3', source: 'n2', target: 'n3' },
  { id: 'e3-4', source: 'n3', target: 'n4' },
  { id: 'e4-5', source: 'n4', target: 'n5' },
]

function statusText(index: number) {
  if (index === 0) return '已完成'
  if (index === 1) return '运行中'
  return '待运行'
}

export function EditorPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNodeId, setSelectedNodeId] = useState<string>('n3')

  const groupedLibrary = useMemo(() => {
    return nodeLibrary.reduce<Record<string, typeof nodeLibrary>>((acc, item) => {
      if (!acc[item.category]) acc[item.category] = []
      acc[item.category].push(item)
      return acc
    }, {})
  }, [])

  const selectedDefinition = useMemo(() => {
    const nodeName = nodes.find((item) => item.id === selectedNodeId)?.data?.label
    return nodeLibrary.find((item) => item.name === nodeName) ?? nodeLibrary[0]
  }, [nodes, selectedNodeId])

  const onConnect = (params: Connection) => {
    setEdges((eds) => addEdge({ ...params, animated: true }, eds))
  }

  const addNodeFromLibrary = (name: string) => {
    const nextId = `n${nodes.length + 1}`
    const nextNode: Node = {
      id: nextId,
      data: { label: name },
      position: { x: 260 + (nodes.length % 3) * 240, y: 280 + (nodes.length % 2) * 160 },
      style: {
        background: '#1f2332',
        color: '#e7eaff',
        border: '1px solid #5661c6',
        borderRadius: 10,
      },
    }
    setNodes((prev) => [...prev, nextNode])
    setSelectedNodeId(nextId)
  }

  return (
    <section className="editor-layout">
      <aside className="editor-left panel">
        <div className="panel-header">
          <h3>节点库</h3>
          <input className="search-input" placeholder="搜索节点" />
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
        </div>
      </aside>

      <div className="editor-canvas panel">
        <div className="panel-header">
          <h3>工作流画布</h3>
          <div className="tag-group">
            <span className="tag">节点 {nodes.length}</span>
            <span className="tag">连线 {edges.length}</span>
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
          <span className="tag">当前节点</span>
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
