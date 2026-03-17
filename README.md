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
│   └── 部署指南.md
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
