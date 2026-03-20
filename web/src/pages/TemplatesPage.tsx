import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { exportTemplateVersionDiff, fetchTemplateVersionDiff, fetchTemplateVersions, rollbackTemplateVersion } from '../api/client'
import { useWorkspace } from '../hooks/useWorkspace'
import type { TemplateVersion, TemplateVersionDiff } from '../types'

export function TemplatesPage() {
  const navigate = useNavigate()
  const { templates, cloneTemplate, toggleTemplateSubscription, updateTemplateMeta, deleteTemplateById } = useWorkspace()
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
      if (menu === 'subscribed' && item.isSubscribed !== true) return false
      if (menu === 'created' && !(item.canManage === true && item.official !== true)) return false
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

  const exportDiff = async (format: 'markdown' | 'csv') => {
    if (!selectedTemplateId || !fromVersion || !toVersion) return
    const blob = await exportTemplateVersionDiff(selectedTemplateId, { fromVersion, toVersion, format })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${selectedTemplateId}-${fromVersion}-to-${toVersion}-diff.${format === 'csv' ? 'csv' : 'md'}`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const onEditTemplate = async (templateId: string) => {
    const current = templates.find((item) => item.id === templateId)
    if (!current) return
    const nextName = window.prompt('模板名称', current.name)
    if (nextName == null) return
    const nextDescription = window.prompt('模板描述', current.description)
    if (nextDescription == null) return
    const nextCategory = window.prompt('模板分类', current.category)
    if (nextCategory == null) return
    const nextGroup = window.prompt('模板分组', current.templateGroup ?? '')
    if (nextGroup == null) return
    const nextTagsRaw = window.prompt('模板标签（逗号分隔）', (current.tags ?? []).join(','))
    if (nextTagsRaw == null) return
    await updateTemplateMeta(templateId, {
      name: nextName,
      description: nextDescription,
      category: nextCategory,
      templateGroup: nextGroup,
      tags: nextTagsRaw
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    })
  }

  const onDeleteTemplate = async (templateId: string) => {
    const confirmed = window.confirm('确认删除该模板？将同时删除版本历史与订阅记录。')
    if (!confirmed) return
    await deleteTemplateById(templateId)
    if (selectedTemplateId === templateId) {
      setSelectedTemplateId(null)
      setVersionRows([])
      setVersionDiff(null)
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
              <th>订阅数</th>
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
                  <span className="tag">{item.subscribedCount ?? 0}</span>
                </td>
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
                    <button
                      type="button"
                      className="button-link ghost"
                      onClick={() => void toggleTemplateSubscription(item.id, item.isSubscribed !== true)}
                    >
                      {item.isSubscribed ? '取消订阅' : '订阅'}
                    </button>
                    <button type="button" className="button-link ghost" onClick={() => void loadTemplateVersions(item.id)}>
                      版本
                    </button>
                    {item.canManage ? (
                      <button type="button" className="button-link ghost" onClick={() => void onEditTemplate(item.id)}>
                        编辑
                      </button>
                    ) : null}
                    {item.canManage ? (
                      <button type="button" className="button-link ghost" onClick={() => void onDeleteTemplate(item.id)}>
                        删除
                      </button>
                    ) : null}
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
                  <button type="button" className="primary ghost mini" onClick={() => void exportDiff('markdown')}>
                    导出 MD
                  </button>
                  <button type="button" className="primary ghost mini" onClick={() => void exportDiff('csv')}>
                    导出 CSV
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
