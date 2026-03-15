import { ArrowRight, CirclePlay } from 'lucide-react'
import { Link } from 'react-router-dom'

export function LandingPage() {
  return (
    <div className="landing">
      <div className="landing-overlay" />
      <div className="landing-content">
        <span className="pill">全能量化交易平台</span>
        <h2>AI 交易新时代已崛起</h2>
        <p>一键创建策略、自动化回测、可视化运行并执行交易。</p>
        <div className="landing-actions">
          <Link to="/workflows" className="primary">
            <CirclePlay size={16} />
            开始研究
          </Link>
          <Link to="/templates" className="primary ghost">
            模板中心
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </div>
  )
}
