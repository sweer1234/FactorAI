import { ArrowRight, CirclePlay } from 'lucide-react'
import { Link } from 'react-router-dom'

export function LandingPage() {
  return (
    <div className="landing">
      <div className="landing-overlay" />
      <div className="landing-content">
        <span className="pill">FactorLab One · 因子研发工作台</span>
        <h2>把研究流程沉淀为可复用资产</h2>
        <p>从数据准备、因子生成到回测评估，全流程可视化编排并支持 Python 深度扩展。</p>
        <div className="landing-actions">
          <Link to="/workflows" className="primary">
            <CirclePlay size={16} />
            进入工作台
          </Link>
          <Link to="/templates" className="primary ghost">
            浏览模板
            <ArrowRight size={16} />
          </Link>
        </div>
        <div className="landing-kv">
          <article>
            <strong>低代码编排</strong>
            <span>节点拖拽可视化，分钟级搭建实验链路</span>
          </article>
          <article>
            <strong>Python 自定义</strong>
            <span>支持自由编写高级因子逻辑与特征处理</span>
          </article>
          <article>
            <strong>报告可追溯</strong>
            <span>运行记录、指标变化、版本信息一体化管理</span>
          </article>
        </div>
      </div>
    </div>
  )
}
