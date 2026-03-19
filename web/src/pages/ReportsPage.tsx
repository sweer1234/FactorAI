import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchWorkflowRunCompare, fetchWorkflowSloView } from '../api/client'
import { useWorkspace } from '../hooks/useWorkspace'
import type { RunCompare, SloView } from '../types'

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

export function ReportsPage() {
  const { workflowId = '' } = useParams()
  const { workflows, runs, backendOnline, getReportByWorkflowId, runWorkflow } = useWorkspace()
  const workflow = workflows.find((item) => item.id === workflowId)
  const report = workflow ? getReportByWorkflowId(workflow.id) : undefined
  const equitySeries = report?.equitySeries ?? []
  const metrics = report?.metrics ?? []
  const layerReturn = report?.layerReturn ?? []
  const [runCompare, setRunCompare] = useState<RunCompare | null>(null)
  const [sloView, setSloView] = useState<SloView | null>(null)

  const workflowRuns = useMemo(
    () => runs.filter((item) => item.workflowId === workflowId).slice(0, 8),
    [runs, workflowId],
  )

  useEffect(() => {
    if (!backendOnline || !workflow?.id) return
    const runIds = workflowRuns.map((item) => item.id)
    const load = async () => {
      try {
        const [compare, slo] = await Promise.all([
          fetchWorkflowRunCompare(workflow.id, runIds),
          fetchWorkflowSloView(workflow.id, { windowSize: 20, p95NodeDurationMs: 900 }),
        ])
        setRunCompare(compare)
        setSloView(slo)
      } catch {
        setRunCompare(null)
        setSloView(null)
      }
    }
    void load()
  }, [backendOnline, workflow?.id, workflowRuns])

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

      <section className="panel">
        <div className="panel-header">
          <h3>SLO 视图（最近 20 次）</h3>
          <span className="tag">{sloView ? pct(sloView.passRate) : '--'}</span>
        </div>
        {sloView ? (
          <>
            <div className="slo-kpis">
              <article>
                <span>通过次数</span>
                <strong>{sloView.passCount}</strong>
              </article>
              <article>
                <span>失败次数</span>
                <strong>{sloView.failCount}</strong>
              </article>
              <article>
                <span>阈值 P95</span>
                <strong>{sloView.thresholds.p95_node_duration_ms}ms</strong>
              </article>
            </div>
            <div className="slo-runs">
              {sloView.runs.slice(-8).map((item) => (
                <div key={String(item.run_id)} className={`slo-run ${item.slo_pass ? 'pass' : 'fail'}`}>
                  <span>{String(item.run_id).slice(-6)}</span>
                  <em>{item.slo_pass ? 'PASS' : 'FAIL'}</em>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="muted">暂无 SLO 数据</p>
        )}
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>多 Run 对比（最近 8 次）</h3>
          <span className="tag">{runCompare?.runIds.length ?? 0}</span>
        </div>
        {runCompare ? (
          <div className="compare-table">
            <table className="table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>状态</th>
                  <th>P95(ms)</th>
                  <th>失败节点</th>
                  <th>WARN</th>
                </tr>
              </thead>
              <tbody>
                {runCompare.runIds.map((runId) => {
                  const item = runCompare.metrics[runId] ?? {}
                  return (
                    <tr key={runId}>
                      <td>{runId.slice(-8)}</td>
                      <td>{String(item.status ?? '--')}</td>
                      <td>{String(item.p95_node_duration_ms ?? '--')}</td>
                      <td>{String(item.failed_nodes ?? '--')}</td>
                      <td>{String(item.warn_logs ?? '--')}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">暂无对比数据</p>
        )}
      </section>
    </div>
  )
}
