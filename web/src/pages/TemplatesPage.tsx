import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '../hooks/useWorkspace'

export function TemplatesPage() {
  const navigate = useNavigate()
  const { templates, cloneTemplate } = useWorkspace()
  const [keyword, setKeyword] = useState('')

  const items = templates.filter((item) => {
    if (!keyword.trim()) return true
    const key = keyword.trim().toLowerCase()
    return (
      item.name.toLowerCase().includes(key) ||
      item.description.toLowerCase().includes(key) ||
      item.tags.join(' ').toLowerCase().includes(key)
    )
  })

  const handleUseTemplate = (templateId: string) => {
    const workflowId = cloneTemplate(templateId)
    if (!workflowId) return
    navigate(`/editor/${workflowId}`)
  }

  return (
    <>
      <section className="panel">
        <div className="panel-header">
          <h3>模板筛选</h3>
          <input
            className="search-input"
            placeholder="搜索模板关键词"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </div>
      </section>
      <section className="template-grid">
        {items.map((item) => (
          <article key={item.id} className="template-card">
            <div className="template-head">
              <h3>{item.name}</h3>
              <span>{item.updatedAt}</span>
            </div>
            <p>{item.description}</p>
            <div className="tag-group">
              {item.tags.map((tag) => (
                <span key={tag} className="tag">
                  {tag}
                </span>
              ))}
            </div>
            <div className="template-actions">
              <button
                type="button"
                className="primary ghost"
                onClick={() => handleUseTemplate(item.id)}
              >
                复制模板
              </button>
              <button type="button" className="primary" onClick={() => handleUseTemplate(item.id)}>
                立即使用
              </button>
            </div>
          </article>
        ))}
        {items.length === 0 ? (
          <article className="template-card empty-card">
            <h3>未匹配到模板</h3>
            <p>可以清空关键词后重试，或先创建空白工作流。</p>
          </article>
        ) : null}
      </section>
    </>
  )
}
