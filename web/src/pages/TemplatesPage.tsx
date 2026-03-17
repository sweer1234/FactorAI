import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useWorkspace } from '../hooks/useWorkspace'

export function TemplatesPage() {
  const navigate = useNavigate()
  const { templates, cloneTemplate } = useWorkspace()
  const [keyword, setKeyword] = useState('')
  const [menu, setMenu] = useState<'official' | 'subscribed' | 'created'>('official')

  const filtered = useMemo(() => {
    const key = keyword.trim().toLowerCase()
    return templates.filter((item) => {
      if (menu === 'official' && item.official === false) return false
      if (!key) return true
      return (
        item.name.toLowerCase().includes(key) ||
        item.description.toLowerCase().includes(key) ||
        item.tags.join(' ').toLowerCase().includes(key) ||
        (item.templateGroup ?? '').toLowerCase().includes(key)
      )
    })
  }, [templates, keyword, menu])

  const handleUseTemplate = async (templateId: string) => {
    const workflowId = await cloneTemplate(templateId)
    if (!workflowId) return
    navigate(`/editor/${workflowId}`)
  }

  return (
    <section className="template-workspace panel">
      <aside className="template-menu">
        <button
          type="button"
          className={`template-menu-item ${menu === 'official' ? 'active' : ''}`}
          onClick={() => setMenu('official')}
        >
          官方模板
        </button>
        <button
          type="button"
          className={`template-menu-item ${menu === 'subscribed' ? 'active' : ''}`}
          onClick={() => setMenu('subscribed')}
        >
          我订阅的
        </button>
        <button
          type="button"
          className={`template-menu-item ${menu === 'created' ? 'active' : ''}`}
          onClick={() => setMenu('created')}
        >
          我创建的
        </button>
      </aside>

      <div className="template-content">
        <div className="panel-header">
          <h3>{menu === 'official' ? '官方模板' : menu === 'subscribed' ? '我订阅的模板' : '我创建的模板'}</h3>
          <input
            className="search-input"
            placeholder="搜索模板关键词"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
        </div>

        <table className="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>分类</th>
              <th>标签</th>
              <th>最近更新时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td>{item.category}</td>
                <td>
                  <div className="tag-group">
                    {(item.tags ?? []).map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                    {item.templateGroup ? <span className="tag">{item.templateGroup}</span> : null}
                  </div>
                </td>
                <td>{item.updatedAt}</td>
                <td>
                  <div className="table-actions">
                    <button type="button" className="button-link" onClick={() => void handleUseTemplate(item.id)}>
                      查看
                    </button>
                    <button
                      type="button"
                      className="button-link ghost"
                      onClick={() => void handleUseTemplate(item.id)}
                    >
                      仿作
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? <p className="muted">当前分类暂无模板，请切换菜单或调整关键词。</p> : null}
      </div>
    </section>
  )
}
