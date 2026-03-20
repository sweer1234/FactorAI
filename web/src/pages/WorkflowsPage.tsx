import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useWorkspace } from '../hooks/useWorkspace'
import type { Workflow } from '../types'

const statusLabel = {
  draft: '草稿',
  running: '运行中',
  published: '已发布',
}

export function WorkflowsPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { workflows, createWorkflow, runWorkflow, publishTemplate } = useWorkspace()
  const [keyword, setKeyword] = useState('')
  const [form, setForm] = useState({
    name: '',
    category: '多因子研究',
    tags: '期货,多因子',
    description: '',
  })
  const [showCreate, setShowCreate] = useState(searchParams.get('create') === '1')

  useEffect(() => {
    setShowCreate(searchParams.get('create') === '1')
  }, [searchParams])

  const items = useMemo(() => {
    if (!keyword.trim()) return workflows
    const key = keyword.trim().toLowerCase()
    return workflows.filter((item) => {
      const tags = item.tags.join(' ').toLowerCase()
      return (
        item.name.toLowerCase().includes(key) ||
        item.category.toLowerCase().includes(key) ||
        tags.includes(key)
      )
    })
  }, [workflows, keyword])

  const openCreate = () => {
    setShowCreate(true)
    setSearchParams({ create: '1' })
  }

  const closeCreate = () => {
    setShowCreate(false)
    setSearchParams({})
  }

  const submitCreate = async () => {
    const name = form.name.trim()
    if (!name) return
    const id = await createWorkflow({
      name,
      category: form.category.trim() || '未分类',
      tags: form.tags
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
      description: form.description.trim() || undefined,
    })
    closeCreate()
    navigate(`/editor/${id}`)
  }

  const updateForm = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const runNow = async (workflow: Workflow) => {
    await runWorkflow(workflow.id)
    navigate('/runs')
  }

  const publishNow = async (workflow: Workflow) => {
    const templateId = await publishTemplate(workflow.id)
    if (!templateId) return
    navigate('/templates')
  }

  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <h3>我的工作流</h3>
          <div className="header-actions">
            <input
              className="search-input"
              placeholder="搜索工作流名称"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
            <button type="button" className="primary" onClick={openCreate}>
              新建工作流
            </button>
          </div>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>分类</th>
              <th>标签</th>
              <th>状态</th>
              <th>最近更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td>{item.category}</td>
                <td>
                  <div className="tag-group">
                    {item.tags.map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                </td>
                <td>
                  <span className={`badge ${item.status}`}>{statusLabel[item.status]}</span>
                </td>
                <td>{item.updatedAt}</td>
                <td>
                  <div className="table-actions">
                    <Link className="button-link" to={`/editor/${item.id}`}>
                      编辑
                    </Link>
                    <button type="button" className="button-link ghost" onClick={() => void runNow(item)}>
                      运行
                    </button>
                    <Link className="button-link ghost" to={`/reports/${item.id}`}>
                      报告
                    </Link>
                    <button type="button" className="button-link ghost" onClick={() => void publishNow(item)}>
                      发布模板
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {showCreate ? (
        <div className="modal-mask" role="presentation">
          <div className="modal-card">
            <h3>新建工作流</h3>
            <label>
              工作流名称
              <input value={form.name} onChange={(event) => updateForm('name', event.target.value)} />
            </label>
            <label>
              分类
              <input
                value={form.category}
                onChange={(event) => updateForm('category', event.target.value)}
              />
            </label>
            <label>
              标签（逗号分隔）
              <input value={form.tags} onChange={(event) => updateForm('tags', event.target.value)} />
            </label>
            <label>
              描述
              <textarea
                value={form.description}
                onChange={(event) => updateForm('description', event.target.value)}
              />
            </label>
            <div className="modal-actions">
              <button type="button" className="primary ghost" onClick={closeCreate}>
                取消
              </button>
              <button type="button" className="primary" onClick={() => void submitCreate()}>
                创建并进入编辑器
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
