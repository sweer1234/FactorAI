import { useMemo } from 'react'
import { equitySeries, layerReturn, reportMetrics } from '../data/mock'

export function ReportsPage() {
  const equityPoints = useMemo(() => {
    const max = Math.max(...equitySeries)
    const min = Math.min(...equitySeries)
    return equitySeries
      .map((value, idx) => {
        const x = (idx / (equitySeries.length - 1)) * 100
        const y = 90 - ((value - min) / (max - min || 1)) * 70
        return `${x},${y}`
      })
      .join(' ')
  }, [])

  return (
    <div className="report-grid">
      <section className="panel">
        <div className="panel-header">
          <h3>核心指标</h3>
        </div>
        <div className="metric-grid">
          {reportMetrics.map((metric) => (
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
          <polyline points={equityPoints} />
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
