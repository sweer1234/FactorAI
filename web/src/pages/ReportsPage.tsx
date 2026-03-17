import { Link, useParams } from 'react-router-dom'
import { useWorkspace } from '../hooks/useWorkspace'

export function ReportsPage() {
  const { workflowId = '' } = useParams()
  const { workflows, getReportByWorkflowId, runWorkflow } = useWorkspace()
  const workflow = workflows.find((item) => item.id === workflowId)
  const report = workflow ? getReportByWorkflowId(workflow.id) : undefined
  const equitySeries = report?.equitySeries ?? []
  const metrics = report?.metrics ?? []
  const layerReturn = report?.layerReturn ?? []

  let equityPoints = ''
  if (equitySeries.length > 0) {
    const max = Math.max(...equitySeries)
    const min = Math.min(...equitySeries)
    equityPoints = equitySeries
      .map((value, idx) => {
        const x = (idx / (equitySeries.length - 1)) * 100
        const y = 90 - ((value - min) / (max - min || 1)) * 70
        return `${x},${y}`
      })
      .join(' ')
  }

  if (!workflow) {
    return (
      <section className="panel empty-state">
        <h3>未找到工作流</h3>
        <p>该工作流可能不存在或已被删除。</p>
        <Link to="/workflows" className="primary">
          返回工作流列表
        </Link>
      </section>
    )
  }

  if (!report) {
    return (
      <section className="panel empty-state">
        <h3>暂无研究报告</h3>
        <p>先运行一次工作流，系统将自动生成因子表现报告。</p>
        <div className="header-actions">
          <button type="button" className="primary" onClick={() => void runWorkflow(workflow.id)}>
            立即运行
          </button>
          <Link to={`/editor/${workflow.id}`} className="primary ghost">
            打开编辑器
          </Link>
        </div>
      </section>
    )
  }

  return (
    <div className="report-grid">
      <section className="panel">
        <div className="panel-header">
          <h3>核心指标 · {report.workflowName}</h3>
          <span className="tag">更新于 {report.updatedAt}</span>
        </div>
        <div className="metric-grid">
          {metrics.map((metric) => (
            <article key={metric.label} className="metric-card">
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em className={metric.trend}>{metric.trend === 'up' ? '↑ 改善' : '↓ 优化中'}</em>
            </article>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>净值曲线（回测）</h3>
        </div>
        <svg viewBox="0 0 100 100" className="line-chart" role="img" aria-label="equity curve">
          {equityPoints ? <polyline points={equityPoints} /> : null}
        </svg>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>分层收益（Q1-Q5）</h3>
        </div>
        <div className="bar-chart">
          {layerReturn.map((item) => (
            <div key={item.layer} className="bar-row">
              <span>{item.layer}</span>
              <div className="bar-track">
                <div
                  className={`bar-fill ${item.value > 0 ? 'positive' : 'negative'}`}
                  style={{ width: `${Math.abs(item.value) * 400}%` }}
                />
              </div>
              <strong>{(item.value * 100).toFixed(1)}%</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
