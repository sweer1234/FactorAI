# FactorAI Web

前端 MVP：仿 PandaAI 风格的因子研究系统，覆盖从工作流管理到因子报告的核心演示链路。

## 本地运行

```bash
npm install
npm run dev
```

默认地址：`http://localhost:5173`

## 构建与预览

```bash
npm run build
npm run preview
```

## 页面路由

- `/` 首页
- `/workflows` 工作流列表
- `/templates` 官方模板
- `/editor/:workflowId` 可视化编辑器
- `/runs` 运行中心
- `/reports/:workflowId` 研究报告
