import { runRecords } from '../data/mock'

const statusLabel = {
  queued: '排队中',
  running: '运行中',
  success: '成功',
  failed: '失败',
}

export function RunsPage() {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>任务队列</h3>
      </div>
      <div className="run-list">
        {runRecords.map((run) => (
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
      </div>
    </section>
  )
}
