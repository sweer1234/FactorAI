# FactorAI

FactorAI 是一个因子研究系统原型，聚焦于：

- 低代码节点化工作流
- Python 节点高自由度扩展
- 因子评估与回测报告可视化

## 项目结构

```text
.
├── docs/                      # 开发文档
│   ├── PRD.md
│   ├── 技术架构.md
│   ├── 节点协议规范.md
│   ├── 开发计划.md
│   ├── 部署指南.md
│   └── 节点库与官方模板仿作开发蓝图V2.md
├── server/                    # 后端服务（FastAPI + SQLite + 执行引擎）
└── web/                       # 前端应用（React + TS + Vite）
```

## 快速开始

后端：

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd web
npm install
npm run dev
```

默认访问地址：`http://localhost:5173`

前端默认请求：`http://localhost:8000/api`

## Cloud Agent 环境预装

仓库已提供 Cloud Agent 环境配置文件：

- `.cursor/environment.json`
- `.cursor/install.sh`

环境启动时会自动预装：

- Python 依赖：`server/requirements.txt`
- Node 依赖：`web/package.json`（优先 `npm ci`）

并可直接在仓库根目录执行：

```bash
python3 -m compileall server/app
npm run lint
npm run build
```

## 鉴权与 RBAC（新增）

后端默认开启基于 Token 的鉴权与角色控制（viewer/editor/admin）：

- `viewer`：只读接口（GET）
- `editor`：运行、保存、上传、回滚等写接口（POST/PUT）
- `admin`：模板版本管理（创建版本、版本回滚）

默认开发 token（可通过 `FACTORAI_AUTH_TOKENS` 覆盖）：

- `dev-viewer-token`
- `dev-editor-token`
- `dev-admin-token`

前端默认会携带 `dev-admin-token`（可通过 `VITE_API_TOKEN` 或 localStorage `factorai_api_token` 覆盖）。

## 任务重试策略（新增）

`POST /api/runs/{run_id}/retry` 支持参数化重试：

- `strategy`: `immediate` / `fixed_backoff`
- `max_attempts`: 1~5
- `backoff_sec`: 0~300

当设置 `max_attempts > 1` 时，失败后会自动按策略继续尝试，直到达到上限。

也可按工作流维度配置默认重试策略：

- `GET /api/workflows/{workflow_id}/run-policy`
- `PUT /api/workflows/{workflow_id}/run-policy`
- `POST /api/runs/batch-action`（批量取消/批量重试）

## 模板发布与版本差异导出（新增）

- `POST /api/workflows/{workflow_id}/publish-template`
- `PUT /api/templates/{template_id}`（模板拥有者或 admin）
- `DELETE /api/templates/{template_id}`（模板拥有者或 admin）
- `POST /api/templates/{template_id}/subscribe`
- `DELETE /api/templates/{template_id}/subscribe`
- `GET /api/templates/{template_id}/versions/diff`
- `GET /api/templates/{template_id}/versions/diff-export?format=markdown|csv`

## 已实现页面（MVP）

1. 首页（品牌入口）
2. 工作流列表
3. 官方模板库
4. 可视化编辑器（节点库 + 画布 + 节点详情）
5. 运行中心
6. 因子研究报告

## 已打通的关键交互

- 创建工作流并跳转编辑器
- 从模板复制生成新工作流
- 编辑器节点增删连线与自动保存
- 保存草稿 / 运行工作流（后端异步执行）
- 运行中心实时刷新任务状态与日志
- 报告按运行结果自动更新
- Python 节点沙箱执行（超时 + 内存限制）

## 后续计划

- 接入真实后端 API 与任务调度
- Python 节点沙箱执行
- 回测引擎与实时行情接入
