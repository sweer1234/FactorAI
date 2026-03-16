import type { NodeDefinition, ReportMetric, RunRecord, Template, Workflow } from '../types'

export const workflowList: Workflow[] = [
  {
    id: 'wf-001',
    name: '因子竞赛-5 PPO融合',
    category: '机器学习 + 因子构建',
    tags: ['量化交易', '机器学习', '强化学习'],
    status: 'published',
    updatedAt: '2026-03-15 00:32:11',
    lastRun: '2026-03-15 00:35:18',
  },
  {
    id: 'wf-002',
    name: '因子竞赛-6 超参搜索',
    category: '超参数优化',
    tags: ['Optuna', 'XGBoost'],
    status: 'running',
    updatedAt: '2026-03-14 21:21:09',
    lastRun: '2026-03-14 21:30:44',
  },
  {
    id: 'wf-003',
    name: '期货跨品种择时策略',
    category: '回测与组合',
    tags: ['CTA', '多因子'],
    status: 'draft',
    updatedAt: '2026-03-13 18:10:51',
  },
]

export const templates: Template[] = [
  {
    id: 'tpl-001',
    name: '因子竞赛-6 趋势搜索',
    description: '特征工程 + 机器学习训练 + 因子分析 + 回测',
    tags: ['官方模板', '趋势'],
    updatedAt: '2026-03-10 09:30:14',
  },
  {
    id: 'tpl-002',
    name: '因子竞赛-4 状态识别',
    description: '状态机 + LightGBM + 分层收益对比',
    tags: ['官方模板', '状态识别'],
    updatedAt: '2026-03-08 17:42:22',
  },
  {
    id: 'tpl-003',
    name: 'PCA 复合因子构建',
    description: '训练模型提取特征重要度后做 PCA 融合',
    tags: ['因子构建', 'PCA'],
    updatedAt: '2026-03-05 11:06:05',
  },
]

export const nodeLibrary: NodeDefinition[] = [
  {
    id: 'basic.python',
    name: 'Python代码输入',
    category: '01-基础工具',
    description: '在节点内执行自定义 Python 代码并输出结构化结果。',
    inputs: ['df_input', 'context'],
    outputs: ['df_factor'],
    params: [
      { key: 'timeout', type: 'number', defaultValue: 300 },
      { key: 'strictSchema', type: 'boolean', defaultValue: true },
    ],
  },
  {
    id: 'feature.build',
    name: '特征工程构建',
    category: '02-特征工程',
    description: '执行去极值、标准化、中性化等预处理。',
    inputs: ['market_df'],
    outputs: ['feature_df'],
    params: [{ key: 'normalize', type: 'boolean', defaultValue: true }],
  },
  {
    id: 'ml.xgboost',
    name: 'XGBoost模型',
    category: '03-机器学习',
    description: '训练 XGBoost 并输出预测值与特征重要性。',
    inputs: ['feature_df', 'label_df'],
    outputs: ['pred_df', 'feature_importance'],
    params: [
      { key: 'maxDepth', type: 'number', defaultValue: 6 },
      { key: 'learningRate', type: 'number', defaultValue: 0.05 },
    ],
  },
  {
    id: 'factor.custom',
    name: '自定义因子构建',
    category: '04-因子相关',
    description: '将模型输出转换为标准因子格式(date/symbol/factor1)。',
    inputs: ['pred_df'],
    outputs: ['factor_df'],
    params: [{ key: 'factorName', type: 'string', defaultValue: 'factor1' }],
  },
  {
    id: 'backtest.future',
    name: '期货回测',
    category: '05-回测相关',
    description: '基于调仓频率和交易成本运行期货策略回测。',
    inputs: ['factor_df'],
    outputs: ['nav_df', 'report_json'],
    params: [
      { key: 'rebalanceDays', type: 'number', defaultValue: 5 },
      { key: 'feeBps', type: 'number', defaultValue: 4 },
    ],
  },
  {
    id: 'factor.pca',
    name: 'PCA因子构建',
    category: '06-线下专属',
    description: '综合模型特征重要度进行 PCA 复合因子生成。',
    inputs: ['feature_importance', 'feature_df'],
    outputs: ['pca_factor'],
    params: [{ key: 'components', type: 'number', defaultValue: 5 }],
  },
]

export const runRecords: RunRecord[] = [
  {
    id: 'run-901',
    workflowName: '因子竞赛-5 PPO融合',
    status: 'success',
    duration: '01m 43s',
    createdAt: '2026-03-15 00:35:18',
    message: '完成 16 个节点，生成回测报告。',
  },
  {
    id: 'run-902',
    workflowName: '因子竞赛-6 超参搜索',
    status: 'running',
    duration: '09m 15s',
    createdAt: '2026-03-14 21:30:44',
    message: '正在执行 Optuna 第 42 轮搜索。',
  },
  {
    id: 'run-903',
    workflowName: '期货跨品种择时策略',
    status: 'failed',
    duration: '00m 21s',
    createdAt: '2026-03-14 20:12:11',
    message: 'Python 节点输出缺失 factor1 字段。',
  },
]

export const reportMetrics: ReportMetric[] = [
  { label: 'IC均值', value: '0.087', trend: 'up' },
  { label: 'RankIC', value: '0.104', trend: 'up' },
  { label: '年化收益', value: '24.8%', trend: 'up' },
  { label: '最大回撤', value: '-7.2%', trend: 'down' },
  { label: '夏普比率', value: '1.91', trend: 'up' },
  { label: '换手率', value: '0.63', trend: 'down' },
]

export const equitySeries = [
  1.0, 1.02, 1.03, 1.01, 1.05, 1.08, 1.06, 1.1, 1.14, 1.12, 1.16, 1.2,
]

export const layerReturn = [
  { layer: 'Q1', value: -0.03 },
  { layer: 'Q2', value: 0.02 },
  { layer: 'Q3', value: 0.06 },
  { layer: 'Q4', value: 0.11 },
  { layer: 'Q5', value: 0.17 },
]
