# FactorAI

FactorAI 是一个仿 PandaAI 风格的因子研究系统原型，聚焦于：

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
│   └── 开发计划.md
└── web/                       # 前端成品（React + TS + Vite）
```

## 快速开始

```bash
cd web
npm install
npm run dev
```

默认访问地址：`http://localhost:5173`

## 已实现页面（MVP）

1. 首页（品牌入口）
2. 工作流列表
3. 官方模板库
4. 可视化编辑器（节点库 + 画布 + 节点详情）
5. 运行中心
6. 因子研究报告

## 后续计划

- 接入真实后端 API 与任务调度
- Python 节点沙箱执行
- 回测引擎与实时行情接入
