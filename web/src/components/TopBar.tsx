import { Bell, Play, Plus, Save } from 'lucide-react'

interface TopBarProps {
  title: string
  subtitle?: string
  showRunActions?: boolean
}

export function TopBar({ title, subtitle, showRunActions }: TopBarProps) {
  return (
    <header className="topbar">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      <div className="topbar-actions">
        <button type="button" className="primary ghost">
          <Bell size={14} />
          通知
        </button>
        {showRunActions ? (
          <>
            <button type="button" className="primary ghost">
              <Save size={14} />
              保存草稿
            </button>
            <button type="button" className="primary">
              <Play size={14} />
              运行工作流
            </button>
          </>
        ) : (
          <button type="button" className="primary">
            <Plus size={14} />
            创建工作流
          </button>
        )}
      </div>
    </header>
  )
}
