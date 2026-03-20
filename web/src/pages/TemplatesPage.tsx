import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchTemplateVersions, rollbackTemplateVersion } from '../api/client'
import { useWorkspace } from '../hooks/useWorkspace'
import type { TemplateVersion } from '../types'

export function TemplatesPage() {
  const navigate = useNavigate()
  const { templates, cloneTemplate } = useWorkspace()
  const [keyword, setKeyword] = useState('')
  const [menu, setMenu] = useState<'official' | 'subscribed' | 'created'>('official')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [versionRows, setVersionRows] = useState<TemplateVersion[]>([])
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [rollingBackVersion, setRollingBackVersion] = useState(false)

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

  const loadTemplateVersions = async (templateId: string) => {
    setSelectedTemplateId(templateId)
    setLoadingVersions(true)
    try {
      const rows = await fetchTemplateVersions(templateId)
      setVersionRows(rows)
    } finally {
      setLoadingVersions(false)
    }
  }

  const onRollbackTemplateVersion = async (templateId: string, version: string) => {
    setRollingBackVersion(true)
    try {
      const result = await rollbackTemplateVersion(templateId, { version })
      setVersionRows((prev) => [result.createdVersion, ...prev])
    } finally {
      setRollingBackVersion(false)
    }
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
                    <button type="button" className="button-link ghost" onClick={() => void loadTemplateVersions(item.id)}>
                      版本
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 ? <p className="muted">当前分类暂无模板，请切换菜单或调整关键词。</p> : null}

        {selectedTemplateId ? (
          <section className="panel">
            <div className="panel-header">
              <h3>模板版本 · {selectedTemplateId}</h3>
              <span className="tag">{loadingVersions ? '加载中' : versionRows.length}</span>
            </div>
            {loadingVersions ? (
              <p className="muted">版本加载中…</p>
            ) : (
              <div className="compare-table">
                <table className="table">
                  <thead>
                    <tr>
                      <th>版本</th>
                      <th>说明</th>
                      <th>时间</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versionRows.map((row) => (
                      <tr key={row.id}>
                        <td>{row.version}</td>
                        <td>{row.changelog || '--'}</td>
                        <td>{row.createdAt}</td>
                        <td>
                          <button
                            type="button"
                            className="button-link ghost"
                            disabled={rollingBackVersion}
                            onClick={() => void onRollbackTemplateVersion(selectedTemplateId, row.version)}
                          >
                            {rollingBackVersion ? '回滚中…' : '回滚到此版本'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {versionRows.length === 0 ? <p className="muted">该模板暂无版本记录</p> : null}
              </div>
            )}
          </section>
        ) : null}
      </div>
    </section>
  )
}
