import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchTemplateVersionDiff, fetchTemplateVersions, rollbackTemplateVersion } from '../api/client'
import { useWorkspace } from '../hooks/useWorkspace'
import type { TemplateVersion, TemplateVersionDiff } from '../types'

export function TemplatesPage() {
  const navigate = useNavigate()
  const { templates, cloneTemplate } = useWorkspace()
  const [keyword, setKeyword] = useState('')
  const [menu, setMenu] = useState<'official' | 'subscribed' | 'created'>('official')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [versionRows, setVersionRows] = useState<TemplateVersion[]>([])
  const [loadingVersions, setLoadingVersions] = useState(false)
  const [rollingBackVersion, setRollingBackVersion] = useState(false)
  const [fromVersion, setFromVersion] = useState('')
  const [toVersion, setToVersion] = useState('')
  const [versionDiff, setVersionDiff] = useState<TemplateVersionDiff | null>(null)
  const [loadingDiff, setLoadingDiff] = useState(false)

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
      setFromVersion(rows[rows.length - 1]?.version ?? '')
      setToVersion(rows[0]?.version ?? '')
      setVersionDiff(null)
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

  const compareTemplateVersions = async () => {
    if (!selectedTemplateId || !fromVersion || !toVersion) return
    setLoadingDiff(true)
    try {
      const diff = await fetchTemplateVersionDiff(selectedTemplateId, fromVersion, toVersion)
      setVersionDiff(diff)
    } finally {
      setLoadingDiff(false)
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
              <>
                <div className="header-actions" style={{ marginBottom: 8 }}>
                  <select value={fromVersion} onChange={(event) => setFromVersion(event.target.value)}>
                    {versionRows.map((row) => (
                      <option key={`from-${row.id}`} value={row.version}>
                        基准 {row.version}
                      </option>
                    ))}
                  </select>
                  <select value={toVersion} onChange={(event) => setToVersion(event.target.value)}>
                    {versionRows.map((row) => (
                      <option key={`to-${row.id}`} value={row.version}>
                        目标 {row.version}
                      </option>
                    ))}
                  </select>
                  <button type="button" className="primary ghost mini" onClick={() => void compareTemplateVersions()} disabled={loadingDiff}>
                    {loadingDiff ? '对比中…' : '版本对比'}
                  </button>
                </div>
                {versionDiff ? (
                  <>
                    <div className="alert-count-grid" style={{ marginBottom: 8 }}>
                      <article>
                        <span>新增节点</span>
                        <strong>{versionDiff.summary.added_nodes ?? 0}</strong>
                      </article>
                      <article>
                        <span>移除节点</span>
                        <strong>{versionDiff.summary.removed_nodes ?? 0}</strong>
                      </article>
                      <article>
                        <span>变更节点</span>
                        <strong>{versionDiff.summary.changed_nodes ?? 0}</strong>
                      </article>
                      <article>
                        <span>边变更</span>
                        <strong>
                          +{versionDiff.summary.added_edges ?? 0} / -{versionDiff.summary.removed_edges ?? 0}
                        </strong>
                      </article>
                    </div>
                    <div className="compare-table" style={{ marginBottom: 8 }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>节点新增</th>
                            <th>节点移除</th>
                            <th>节点变更</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>{versionDiff.addedNodes.slice(0, 6).join('，') || '--'}</td>
                            <td>{versionDiff.removedNodes.slice(0, 6).join('，') || '--'}</td>
                            <td>{versionDiff.changedNodes.slice(0, 6).join('，') || '--'}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                    <div className="compare-table" style={{ marginBottom: 8 }}>
                      <table className="table">
                        <thead>
                          <tr>
                            <th>新增边</th>
                            <th>移除边</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>{versionDiff.addedEdges.slice(0, 6).join('，') || '--'}</td>
                            <td>{versionDiff.removedEdges.slice(0, 6).join('，') || '--'}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : null}
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
              </>
            )}
          </section>
        ) : null}
      </div>
    </section>
  )
}
