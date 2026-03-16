import { Link } from 'react-router-dom'
import { workflowList } from '../data/mock'

const statusLabel = {
  draft: '草稿',
  running: '运行中',
  published: '已发布',
}

export function WorkflowsPage() {
  return (
    <section className="panel">
      <div className="panel-header">
        <h3>我的工作流</h3>
        <input className="search-input" placeholder="搜索工作流名称" />
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>分类</th>
            <th>标签</th>
            <th>状态</th>
            <th>最近更新时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {workflowList.map((item) => (
            <tr key={item.id}>
              <td>{item.name}</td>
              <td>{item.category}</td>
              <td>
                <div className="tag-group">
                  {item.tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              </td>
              <td>
                <span className={`badge ${item.status}`}>{statusLabel[item.status]}</span>
              </td>
              <td>{item.updatedAt}</td>
              <td>
                <div className="table-actions">
                  <Link className="button-link" to={`/editor/${item.id}`}>
                    查看
                  </Link>
                  <Link className="button-link ghost" to={`/reports/${item.id}`}>
                    报告
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
