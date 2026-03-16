import { Link } from 'react-router-dom'
import { templates } from '../data/mock'

export function TemplatesPage() {
  return (
    <section className="template-grid">
      {templates.map((item) => (
        <article key={item.id} className="template-card">
          <div className="template-head">
            <h3>{item.name}</h3>
            <span>{item.updatedAt}</span>
          </div>
          <p>{item.description}</p>
          <div className="tag-group">
            {item.tags.map((tag) => (
              <span key={tag} className="tag">
                {tag}
              </span>
            ))}
          </div>
          <div className="template-actions">
            <button type="button" className="primary ghost">
              复制模板
            </button>
            <Link to="/editor/wf-001" className="primary">
              立即使用
            </Link>
          </div>
        </article>
      ))}
    </section>
  )
}
