# FactorAI Server

后端服务基于 FastAPI，提供以下能力：

- 工作流、模板、运行记录、报告的持久化 API
- 工作流 DAG 执行引擎（异步后台执行）
- Python 节点沙箱（超时 + 内存限制 + 字段校验）
- 简化回测计算（IC/RankIC/收益/回撤等）

## 快速启动

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认接口前缀：`/api`

## 关键接口

- `GET /api/workflows`
- `POST /api/workflows`
- `PUT /api/workflows/{id}/graph`
- `POST /api/workflows/{id}/run`
- `GET /api/runs`
- `GET /api/reports/{workflow_id}`
- `GET /api/templates`
- `POST /api/templates/{id}/clone`
- `GET /api/node-library`
