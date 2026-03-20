import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { useWorkspace } from '../hooks/useWorkspace'

const pageConfig: Record<string, { title: string; subtitle: string; runActions?: boolean }> = {
  '/workflows': {
    title: '量化工作流',
    subtitle: '管理你的因子研究、回测和发布流程。',
  },
  '/templates': {
    title: '官方模板库',
    subtitle: '快速复制成熟研究模板，缩短实验周期。',
  },
  '/runs': {
    title: '运行中心',
    subtitle: '查看任务队列、日志和失败原因。',
  },
}

function resolveConfig(pathname: string) {
  if (pathname.startsWith('/editor')) {
    return {
      title: '可视化工作流编辑器',
      subtitle: '节点化构建研究链路，支持 Python 节点扩展。',
      runActions: true,
    }
  }
  if (pathname.startsWith('/reports')) {
    return {
      title: '因子研究报告',
      subtitle: '关注 IC、分层收益与风险稳定性。',
    }
  }
  return pageConfig[pathname] ?? { title: 'FactorLab One', subtitle: 'AI 因子研究系统' }
}

export function AppShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const { runWorkflow, saveWorkflowDraft, notice, backendOnline, loading } = useWorkspace()
  const config = resolveConfig(location.pathname)
  const workflowId = location.pathname.startsWith('/editor/')
    ? location.pathname.replace('/editor/', '')
    : undefined

  const onCreateWorkflow = () => {
    navigate('/workflows?create=1')
  }

  const onSaveDraft = () => {
    if (!workflowId) return
    void saveWorkflowDraft(workflowId)
  }

  const onRunWorkflow = () => {
    if (!workflowId) return
    void runWorkflow(workflowId)
  }

  return (
    <div className="layout">
      <Sidebar />
      <main className="content">
        <TopBar
          title={loading ? `${config.title}（加载中）` : config.title}
          subtitle={config.subtitle}
          showRunActions={config.runActions}
          onCreateWorkflow={onCreateWorkflow}
          onSaveDraft={onSaveDraft}
          onRunWorkflow={onRunWorkflow}
        />
        <div className="content-body">
          {!backendOnline ? <p className="offline-tip">后端未连接，当前运行在本地演示模式。</p> : null}
          <Outlet />
        </div>
        {notice ? <div className="toast">{notice}</div> : null}
      </main>
    </div>
  )
}
