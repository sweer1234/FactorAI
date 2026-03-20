import { useMemo, useState } from 'react'
import { useWorkspace } from '../hooks/useWorkspace'

const statusLabel = {
  queued: '排队中',
  running: '运行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

export function RunsPage() {
  const { runs, cancelRunById, retryRunById, batchRunAction } = useWorkspace()
  const [statusFilter, setStatusFilter] = useState<'all' | 'queued' | 'running' | 'success' | 'failed' | 'cancelled'>(
    'all',
  )
  const [retryStrategy, setRetryStrategy] = useState<'immediate' | 'fixed_backoff'>('immediate')
  const [retryAttempts, setRetryAttempts] = useState(1)
  const [retryBackoffSec, setRetryBackoffSec] = useState(0)
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([])

  const filteredRuns = useMemo(() => {
    if (statusFilter === 'all') return runs
    return runs.filter((item) => item.status === statusFilter)
  }, [runs, statusFilter])

  const toggleSelected = (runId: string, checked: boolean) => {
    setSelectedRunIds((prev) => (checked ? Array.from(new Set([...prev, runId])) : prev.filter((item) => item !== runId)))
  }

  const toggleSelectAllFiltered = (checked: boolean) => {
    const ids = filteredRuns.map((item) => item.id)
    setSelectedRunIds((prev) => (checked ? Array.from(new Set([...prev, ...ids])) : prev.filter((item) => !ids.includes(item))))
  }

  const runSelection = useMemo(() => {
    const rows = runs.filter((item) => selectedRunIds.includes(item.id))
    return {
      total: rows.length,
      cancelable: rows.filter((item) => item.status === 'queued' || item.status === 'running').map((item) => item.id),
      retryable: rows.filter((item) => item.status === 'failed' || item.status === 'cancelled').map((item) => item.id),
    }
  }, [runs, selectedRunIds])

  return (
    <section className="panel">
      <div className="panel-header">
        <h3>任务队列</h3>
        <div className="header-actions">
          <span className="tag">总数 {runs.length}</span>
          <span className="tag">已选 {runSelection.total}</span>
          <select value={retryStrategy} onChange={(event) => setRetryStrategy(event.target.value as typeof retryStrategy)}>
            <option value="immediate">重试策略: 立即</option>
            <option value="fixed_backoff">重试策略: 固定退避</option>
          </select>
          <input
            className="search-input"
            style={{ width: 120 }}
            type="number"
            min={1}
            max={5}
            value={retryAttempts}
            onChange={(event) => setRetryAttempts(Number(event.target.value || 1))}
            placeholder="最大尝试"
          />
          <input
            className="search-input"
            style={{ width: 120 }}
            type="number"
            min={0}
            max={300}
            value={retryBackoffSec}
            onChange={(event) => setRetryBackoffSec(Number(event.target.value || 0))}
            placeholder="退避秒数"
          />
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">全部状态</option>
            <option value="queued">排队中</option>
            <option value="running">运行中</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
            <option value="cancelled">已取消</option>
          </select>
          <button
            type="button"
            className="primary ghost mini"
            disabled={runSelection.cancelable.length === 0}
            onClick={() => void batchRunAction({ action: 'cancel', runIds: runSelection.cancelable })}
          >
            批量取消
          </button>
          <button
            type="button"
            className="primary ghost mini"
            disabled={runSelection.retryable.length === 0}
            onClick={() =>
              void batchRunAction({
                action: 'retry',
                runIds: runSelection.retryable,
                retry: {
                  strategy: retryStrategy,
                  maxAttempts: retryAttempts,
                  backoffSec: retryBackoffSec,
                },
              })
            }
          >
            批量重试
          </button>
        </div>
      </div>
      <div className="run-list">
        <article className="run-card">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={filteredRuns.length > 0 && filteredRuns.every((item) => selectedRunIds.includes(item.id))}
              onChange={(event) => toggleSelectAllFiltered(event.target.checked)}
            />
            全选当前筛选列表
          </label>
        </article>
        {filteredRuns.map((run) => (
          <article key={run.id} className="run-card">
            <div className="run-title">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={selectedRunIds.includes(run.id)}
                  onChange={(event) => toggleSelected(run.id, event.target.checked)}
                />
              </label>
              <h4>{run.workflowName}</h4>
              <span className={`badge ${run.status}`}>{statusLabel[run.status]}</span>
            </div>
            <p>{run.message}</p>
            {run.logs && run.logs.length > 0 ? (
              <details className="run-logs">
                <summary>查看日志</summary>
                <pre>{run.logs.join('\n')}</pre>
              </details>
            ) : null}
            <div className="run-meta">
              <span>任务ID: {run.id}</span>
              <span>耗时: {run.duration}</span>
              <span>开始时间: {run.createdAt}</span>
              {run.retryAttempt ? <span>重试尝试: {run.retryAttempt}/{run.retryMaxAttempts ?? 1}</span> : null}
              {run.retriedFromRunId ? <span>来源任务: {run.retriedFromRunId.slice(-8)}</span> : null}
            </div>
            <div className="table-actions">
              {(run.status === 'queued' || run.status === 'running') && (
                <button type="button" className="button-link ghost" onClick={() => void cancelRunById(run.id)}>
                  取消
                </button>
              )}
              {(run.status === 'failed' || run.status === 'cancelled') && (
                <button
                  type="button"
                  className="button-link ghost"
                  onClick={() =>
                    void retryRunById(run.id, {
                      strategy: retryStrategy,
                      maxAttempts: retryAttempts,
                      backoffSec: retryBackoffSec,
                    })
                  }
                >
                  重试
                </button>
              )}
            </div>
          </article>
        ))}
        {filteredRuns.length === 0 ? <article className="run-card">当前筛选条件下暂无任务。</article> : null}
      </div>
    </section>
  )
}
