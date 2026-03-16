import { BarChart3, ClipboardList, FileClock, Home, LayoutTemplate, Workflow } from 'lucide-react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: '首页', icon: Home, end: true },
  { to: '/workflows', label: '工作流', icon: Workflow },
  { to: '/templates', label: '官方模板', icon: LayoutTemplate },
  { to: '/runs', label: '运行中心', icon: FileClock },
  { to: '/reports/wf-001', label: '研究报告', icon: BarChart3 },
  { to: '/editor/wf-001', label: '编辑器', icon: ClipboardList },
]

export function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-logo">F</div>
        <div>
          <p className="brand-title">FactorLab One</p>
          <p className="brand-subtitle">Research Studio</p>
        </div>
      </div>
      <nav className="nav-list">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>
      <div className="sidebar-footer">
        <span className="quota">999 算力</span>
        <button type="button" className="primary ghost">
          升级资源
        </button>
      </div>
    </aside>
  )
}
