import { Bell, Play, Plus, Save } from 'lucide-react'

interface TopBarProps {
  title: string
  subtitle?: string
  showRunActions?: boolean
  onCreateWorkflow?: () => void
  onSaveDraft?: () => void
  onRunWorkflow?: () => void
}

export function TopBar({
  title,
  subtitle,
  showRunActions,
  onCreateWorkflow,
  onSaveDraft,
  onRunWorkflow,
}: TopBarProps) {
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
            <button type="button" className="primary ghost" onClick={onSaveDraft}>
              <Save size={14} />
              保存草稿
            </button>
            <button type="button" className="primary" onClick={onRunWorkflow}>
              <Play size={14} />
              运行工作流
            </button>
          </>
        ) : (
          <button type="button" className="primary" onClick={onCreateWorkflow}>
            <Plus size={14} />
            创建工作流
          </button>
        )}
      </div>
    </header>
  )
}
