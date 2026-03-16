import { useMemo, useState } from 'react'
import { useWorkspace } from '../hooks/useWorkspace'

const statusLabel = {
  queued: '排队中',
  running: '运行中',
  success: '成功',
  failed: '失败',
}

export function RunsPage() {
  const { runs } = useWorkspace()
  const [statusFilter, setStatusFilter] = useState<'all' | 'queued' | 'running' | 'success' | 'failed'>('all')

  const filteredRuns = useMemo(() => {
    if (statusFilter === 'all') return runs
    return runs.filter((item) => item.status === statusFilter)
  }, [runs, statusFilter])

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>任务队列</h3>
        <div className="header-actions">
          <span className="tag">总数 {runs.length}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">全部状态</option>
            <option value="queued">排队中</option>
            <option value="running">运行中</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
          </select>
        </div>
      </div>
      <div className="run-list">
        {filteredRuns.map((run) => (
          <article key={run.id} className="run-card">
            <div className="run-title">
              <h4>{run.workflowName}</h4>
              <span className={`badge ${run.status}`}>{statusLabel[run.status]}</span>
            </div>
            <p>{run.message}</p>
            <div className="run-meta">
              <span>任务ID: {run.id}</span>
              <span>耗时: {run.duration}</span>
              <span>开始时间: {run.createdAt}</span>
            </div>
          </article>
        ))}
        {filteredRuns.length === 0 ? <article className="run-card">当前筛选条件下暂无任务。</article> : null}
      </div>
    </section>
  )
}
