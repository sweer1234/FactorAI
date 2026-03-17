from __future__ import annotations

from datetime import datetime
from typing import Any


def _now_text() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def make_node_spec(
    *,
    node_id: str,
    name: str,
    category: str,
    description: str,
    inputs: list[str],
    outputs: list[str],
    params: list[dict[str, Any]],
    intro: str | None = None,
    workflow_example: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "name": name,
        "category": category,
        "description": description,
        "inputs": inputs,
        "outputs": outputs,
        "params": params,
        "doc": {
            "intro": intro or description,
            "workflow_example": workflow_example
            or f"典型链路：数据准备 -> {name} -> 因子分析/回测 -> 结果输出",
            "notes": notes
            or [
                "建议先在小样本上调试参数，再扩展到全样本运行。",
                "确保输入数据包含 date 与 symbol 字段。",
            ],
        },
        "runtime": {"engine": "python", "timeout_sec": 120, "memory_mb": 1024},
    }


NODE_LIBRARY_CATALOG: list[dict[str, Any]] = [
    # 01-基础工具
    make_node_spec(
        node_id="basic.python",
        name="Python代码输入",
        category="01-基础工具",
        description="在节点内执行自定义 Python 代码并输出结构化结果。",
        inputs=["df_input"],
        outputs=["df_factor"],
        params=[
            {"key": "timeout", "type": "number", "defaultValue": 6},
            {"key": "strictSchema", "type": "boolean", "defaultValue": True},
            {"key": "script", "type": "string", "defaultValue": "df_factor = df_input.copy()"},
        ],
        intro="可直接编写 Python 逻辑构建自定义因子，适用于复杂实验。",
        notes=[
            "输出必须包含 date/symbol/factor1 三列。",
            "代码中避免长时间阻塞操作，超过超时会被终止。",
        ],
    ),
    make_node_spec(
        node_id="basic.formula",
        name="公式输入",
        category="01-基础工具",
        description="通过公式表达式快速构建基础特征与标签。",
        inputs=["market_df"],
        outputs=["formula_df"],
        params=[{"key": "formula", "type": "string", "defaultValue": "close / delay(close, 1) - 1"}],
    ),
    make_node_spec(
        node_id="basic.model_upload",
        name="模型上传",
        category="01-基础工具",
        description="上传已训练模型并注入当前工作流。",
        inputs=[],
        outputs=["model_obj"],
        params=[{"key": "path", "type": "string", "defaultValue": "models/model.pkl"}],
    ),
    make_node_spec(
        node_id="basic.loop_control",
        name="循环控制",
        category="01-基础工具",
        description="按时间段或参数网格循环执行子流程。",
        inputs=["dataset"],
        outputs=["loop_result"],
        params=[{"key": "loop_mode", "type": "select", "options": ["time", "grid"], "defaultValue": "time"}],
    ),
    make_node_spec(
        node_id="basic.model_download",
        name="模型下载",
        category="01-基础工具",
        description="将训练结果模型打包下载。",
        inputs=["model_obj"],
        outputs=["artifact_url"],
        params=[{"key": "format", "type": "select", "options": ["pkl", "onnx"], "defaultValue": "pkl"}],
    ),
    make_node_spec(
        node_id="basic.data_download",
        name="数据下载",
        category="01-基础工具",
        description="导出中间结果或最终因子数据。",
        inputs=["df_factor"],
        outputs=["artifact_url"],
        params=[{"key": "file_type", "type": "select", "options": ["csv", "parquet"], "defaultValue": "csv"}],
    ),
    # 02-特征工程
    make_node_spec(
        node_id="feature.build",
        name="特征工程构建",
        category="02-特征工程",
        description="执行去极值、标准化、缺失处理与标签生成。",
        inputs=["market_df"],
        outputs=["feature_df", "label_df"],
        params=[
            {"key": "winsorize", "type": "boolean", "defaultValue": True},
            {"key": "normalize", "type": "boolean", "defaultValue": True},
            {"key": "label_expr", "type": "string", "defaultValue": "future_return(close, 1)"},
        ],
    ),
    # 03-机器学习（11）
    make_node_spec(
        node_id="ml.mlp",
        name="MLP模型",
        category="03-机器学习",
        description="使用多层感知机训练并输出预测分数。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "hidden_layers", "type": "string", "defaultValue": "128,64"}],
    ),
    make_node_spec(
        node_id="ml.svm",
        name="SVM模型",
        category="03-机器学习",
        description="使用支持向量机训练分类/回归模型。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "kernel", "type": "select", "options": ["rbf", "linear"], "defaultValue": "rbf"}],
    ),
    make_node_spec(
        node_id="ml.lightgbm",
        name="LightGBM模型",
        category="03-机器学习",
        description="使用 LightGBM 训练并输出特征重要度。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "feature_importance", "model_obj"],
        params=[{"key": "num_leaves", "type": "number", "defaultValue": 31}],
    ),
    make_node_spec(
        node_id="ml.gru",
        name="GRU模型",
        category="03-机器学习",
        description="基于时序窗口训练 GRU 网络。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "window", "type": "number", "defaultValue": 20}],
    ),
    make_node_spec(
        node_id="ml.lstm",
        name="LSTM模型",
        category="03-机器学习",
        description="基于时序窗口训练 LSTM 网络。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "window", "type": "number", "defaultValue": 30}],
    ),
    make_node_spec(
        node_id="ml.cnn",
        name="CNN模型",
        category="03-机器学习",
        description="使用卷积结构提取局部模式并预测。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "channels", "type": "number", "defaultValue": 32}],
    ),
    make_node_spec(
        node_id="ml.optuna",
        name="超参数搜索(Optuna)",
        category="03-机器学习",
        description="自动搜索模型参数并输出最优参数集。",
        inputs=["feature_df", "label_df"],
        outputs=["best_params", "model_obj"],
        params=[{"key": "trials", "type": "number", "defaultValue": 50}],
    ),
    make_node_spec(
        node_id="ml.xgboost",
        name="Xgboost模型",
        category="03-机器学习",
        description="训练 XGBoost 模型并输出预测与特征重要度。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "feature_importance", "model_obj"],
        params=[
            {"key": "max_depth", "type": "number", "defaultValue": 6},
            {"key": "eta", "type": "number", "defaultValue": 0.05},
        ],
    ),
    make_node_spec(
        node_id="ml.gnn",
        name="GNN模型",
        category="03-机器学习",
        description="基于图结构信息训练 GNN 因子模型。",
        inputs=["graph_feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "hidden_dim", "type": "number", "defaultValue": 64}],
    ),
    make_node_spec(
        node_id="ml.random_forest",
        name="随机森林模型",
        category="03-机器学习",
        description="训练随机森林并输出预测分数。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "n_estimators", "type": "number", "defaultValue": 200}],
    ),
    make_node_spec(
        node_id="ml.transformer",
        name="Transformer模型",
        category="03-机器学习",
        description="使用 Transformer 架构进行时序预测。",
        inputs=["feature_df", "label_df"],
        outputs=["pred_df", "model_obj"],
        params=[{"key": "heads", "type": "number", "defaultValue": 4}],
    ),
    # 04-因子相关（12）
    make_node_spec(
        node_id="factor.analysis_future",
        name="因子分析(期货)",
        category="04-因子相关",
        description="对期货因子进行分组回测与绩效评估。",
        inputs=["df_factor"],
        outputs=["analysis_report"],
        params=[{"key": "group_num", "type": "number", "defaultValue": 5}],
        intro="该节点用于期货场景的因子分层分析，评估因子有效性与稳定性。",
        notes=[
            "建议在样本内与样本外分别运行，观察表现一致性。",
            "若换手较高，请在后续回测节点中提高交易成本参数。",
        ],
    ),
    make_node_spec(
        node_id="factor.contest_entry",
        name="因子大赛参赛节点",
        category="04-因子相关",
        description="将因子结果封装为参赛标准输出格式。",
        inputs=["df_factor"],
        outputs=["contest_artifact"],
        params=[{"key": "market_type", "type": "select", "options": ["期货", "股票"], "defaultValue": "期货"}],
    ),
    make_node_spec(
        node_id="factor.linear_build",
        name="线性因子构建",
        category="04-因子相关",
        description="对多特征做线性加权构建因子。",
        inputs=["feature_df"],
        outputs=["df_factor"],
        params=[{"key": "weights", "type": "string", "defaultValue": "0.4,0.3,0.3"}],
    ),
    make_node_spec(
        node_id="factor.nonlinear_build",
        name="非线性因子构建",
        category="04-因子相关",
        description="通过非线性模型输出构建复合因子。",
        inputs=["feature_df", "model_obj"],
        outputs=["df_factor"],
        params=[{"key": "model_type", "type": "select", "options": ["xgboost", "lgbm"], "defaultValue": "xgboost"}],
    ),
    make_node_spec(
        node_id="factor.custom_build",
        name="自定义因子构建",
        category="04-因子相关",
        description="按自定义逻辑输出标准因子列。",
        inputs=["feature_df"],
        outputs=["df_factor"],
        params=[{"key": "formula", "type": "string", "defaultValue": "(f1 + f2) / 2"}],
    ),
    make_node_spec(
        node_id="factor.weight_adjust",
        name="因子权重调整",
        category="04-因子相关",
        description="对多个子因子权重进行再分配。",
        inputs=["factor_pool"],
        outputs=["weighted_factor"],
        params=[{"key": "method", "type": "select", "options": ["equal", "ic_weight"], "defaultValue": "ic_weight"}],
    ),
    make_node_spec(
        node_id="factor.merge",
        name="多因子合并",
        category="04-因子相关",
        description="按字段拼接多个因子结果。",
        inputs=["factor_a", "factor_b"],
        outputs=["factor_pool"],
        params=[{"key": "join_type", "type": "select", "options": ["inner", "left"], "defaultValue": "inner"}],
    ),
    make_node_spec(
        node_id="factor.combine",
        name="多因子组合",
        category="04-因子相关",
        description="将因子池组合为最终交易因子。",
        inputs=["factor_pool"],
        outputs=["df_factor"],
        params=[{"key": "combine_mode", "type": "select", "options": ["rank_sum", "zscore_sum"], "defaultValue": "rank_sum"}],
    ),
    make_node_spec(
        node_id="factor.corr_analysis",
        name="因子相关性分析",
        category="04-因子相关",
        description="计算因子间相关矩阵并识别冗余因子。",
        inputs=["factor_pool"],
        outputs=["corr_matrix"],
        params=[{"key": "corr_method", "type": "select", "options": ["pearson", "spearman"], "defaultValue": "spearman"}],
    ),
    make_node_spec(
        node_id="factor.corr_result",
        name="因子相关性分析结果",
        category="04-因子相关",
        description="展示并导出相关性分析结果。",
        inputs=["corr_matrix"],
        outputs=["report_json"],
        params=[{"key": "threshold", "type": "number", "defaultValue": 0.8}],
    ),
    make_node_spec(
        node_id="factor.analysis",
        name="因子分析",
        category="04-因子相关",
        description="对因子进行通用有效性分析（IC/分层/稳定性）。",
        inputs=["df_factor"],
        outputs=["analysis_report"],
        params=[{"key": "group_num", "type": "number", "defaultValue": 10}],
    ),
    make_node_spec(
        node_id="factor.analysis_result",
        name="因子分析结果",
        category="04-因子相关",
        description="聚合因子分析输出并提供全屏查看。",
        inputs=["analysis_report"],
        outputs=["result_json"],
        params=[{"key": "display_mode", "type": "select", "options": ["summary", "full"], "defaultValue": "summary"}],
    ),
    # 05-回测相关（3）
    make_node_spec(
        node_id="backtest.stock",
        name="股票回测",
        category="05-回测相关",
        description="按股票交易规则执行策略回测。",
        inputs=["df_factor"],
        outputs=["backtest_report"],
        params=[{"key": "capital", "type": "number", "defaultValue": 1000000}],
    ),
    make_node_spec(
        node_id="backtest.future",
        name="期货回测",
        category="05-回测相关",
        description="按期货交易规则执行策略回测。",
        inputs=["df_factor"],
        outputs=["backtest_report"],
        params=[{"key": "fee_bps", "type": "number", "defaultValue": 4}],
    ),
    make_node_spec(
        node_id="backtest.strategy_result",
        name="策略回测结果",
        category="05-回测相关",
        description="展示策略回测报告并支持全屏查看。",
        inputs=["backtest_report"],
        outputs=["result_json"],
        params=[{"key": "show_detail", "type": "boolean", "defaultValue": True}],
    ),
    # 06-线下课专属（10）
    make_node_spec(
        node_id="offline.ic",
        name="因子IC计算",
        category="06-线下课专属",
        description="计算因子 IC/RankIC 与时序稳定性。",
        inputs=["df_factor"],
        outputs=["ic_report"],
        params=[{"key": "horizon", "type": "number", "defaultValue": 1}],
    ),
    make_node_spec(
        node_id="offline.pca",
        name="PCA因子构建",
        category="06-线下课专属",
        description="基于 PCA 降维构建复合因子。",
        inputs=["feature_df"],
        outputs=["df_factor"],
        params=[{"key": "components", "type": "number", "defaultValue": 5}],
    ),
    make_node_spec(
        node_id="offline.multi_ml",
        name="多因子构建(机器学习)",
        category="06-线下课专属",
        description="融合多个机器学习模型输出构建因子。",
        inputs=["pred_a", "pred_b"],
        outputs=["df_factor"],
        params=[{"key": "blend_mode", "type": "select", "options": ["avg", "rank_avg"], "defaultValue": "rank_avg"}],
    ),
    make_node_spec(
        node_id="offline.industry_propagation",
        name="行业传导计算节点",
        category="06-线下课专属",
        description="计算行业因子的传导效应与滞后影响。",
        inputs=["industry_feature_df"],
        outputs=["industry_factor"],
        params=[{"key": "lag", "type": "number", "defaultValue": 3}],
    ),
    make_node_spec(
        node_id="offline.formula_split",
        name="公式拆分",
        category="06-线下课专属",
        description="将复杂公式拆解为可复用子表达式。",
        inputs=["formula_df"],
        outputs=["split_formula_df"],
        params=[{"key": "max_depth", "type": "number", "defaultValue": 4}],
    ),
    make_node_spec(
        node_id="offline.single_model_multi_feature",
        name="因子构建(机器学习-单模型多特征)",
        category="06-线下课专属",
        description="单模型多特征场景下批量构建因子。",
        inputs=["feature_df", "label_df"],
        outputs=["df_factor"],
        params=[{"key": "model_type", "type": "select", "options": ["xgboost", "lightgbm"], "defaultValue": "xgboost"}],
    ),
    make_node_spec(
        node_id="offline.weight_combo",
        name="因子权重组合节点",
        category="06-线下课专属",
        description="在预测窗口内动态调整因子权重。",
        inputs=["factor_pool"],
        outputs=["weighted_factor"],
        params=[{"key": "rebalance_days", "type": "number", "defaultValue": 5}],
    ),
    make_node_spec(
        node_id="offline.spearman",
        name="Spearman因子构建",
        category="06-线下课专属",
        description="通过 Spearman 排序相关构建稳健因子。",
        inputs=["feature_df", "model_obj"],
        outputs=["df_factor"],
        params=[{"key": "lookback", "type": "number", "defaultValue": 60}],
        intro="批量计算因子与目标值的 Spearman 相关，形成稳健排序因子。",
        notes=[
            "特征列需与训练时保持一致，避免列顺序变化导致结果偏移。",
            "首行若无法 shift 预测，建议在后处理阶段去除。",
        ],
    ),
    make_node_spec(
        node_id="offline.alphagen_upload",
        name="因子AlphaGen上传",
        category="06-线下课专属",
        description="上传 AlphaGen 生成的模型或表达式产物。",
        inputs=[],
        outputs=["alphagen_obj"],
        params=[{"key": "artifact_path", "type": "string", "defaultValue": "alphagen/model.bin"}],
    ),
    make_node_spec(
        node_id="offline.formula_transform",
        name="公式转换",
        category="06-线下课专属",
        description="将表达式转换为目标平台可执行格式。",
        inputs=["formula_df"],
        outputs=["converted_formula"],
        params=[{"key": "target", "type": "select", "options": ["pandas", "sql"], "defaultValue": "pandas"}],
    ),
]


NODE_SPEC_BY_ID: dict[str, dict[str, Any]] = {item["id"]: item for item in NODE_LIBRARY_CATALOG}
NODE_SPEC_BY_NAME: dict[str, dict[str, Any]] = {item["name"]: item for item in NODE_LIBRARY_CATALOG}


def _style_from_category(category: str) -> str:
    if category.startswith("01"):
        return "data"
    if category.startswith("02"):
        return "feature"
    if category.startswith("03"):
        return "model"
    if category.startswith("04"):
        return "factor"
    if category.startswith("05"):
        return "backtest"
    return "default"


def _default_params(node_spec_id: str) -> dict[str, Any]:
    spec = NODE_SPEC_BY_ID.get(node_spec_id)
    if not spec:
        return {}
    result: dict[str, Any] = {}
    for item in spec.get("params", []):
        result[item["key"]] = item.get("defaultValue")
    return result


def _node(node_id: str, label: str, x: int, y: int, *, node_spec_id: str | None = None, params: dict[str, Any] | None = None):
    spec = NODE_SPEC_BY_ID.get(node_spec_id or NODE_SPEC_BY_NAME.get(label, {}).get("id", ""))
    return {
        "id": node_id,
        "label": label,
        "position": {"x": x, "y": y},
        "styleVariant": _style_from_category(spec["category"]) if spec else "default",
        "nodeSpecId": spec["id"] if spec else node_spec_id,
        "params": {**(_default_params(spec["id"]) if spec else {}), **(params or {})},
    }


def graph_from_labels(labels: list[str]) -> dict[str, Any]:
    x0 = 40
    spacing = 220
    nodes = []
    edges = []
    for idx, label in enumerate(labels):
        node_id = f"n{idx+1}"
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "position": {"x": x0 + idx * spacing, "y": 140},
                "styleVariant": "feature" if "特征" in label else "model" if "模型" in label else "factor",
            }
        )
        if idx > 0:
            edges.append({"id": f"e{idx}", "source": f"n{idx}", "target": node_id, "animated": idx % 2 == 1})
    return {"nodes": nodes, "edges": edges}


def _graph_official_06() -> dict[str, Any]:
    nodes = [
        _node("n1", "公式输入", 40, 220),
        _node("n2", "特征工程构建", 270, 220),
        _node("n3", "超参数搜索(Optuna)", 500, 90),
        _node("n4", "Xgboost模型", 500, 280),
        _node("n5", "因子构建(机器学习)", 760, 220, node_spec_id="offline.multi_ml"),
        _node("n6", "因子大赛参赛节点", 1010, 130),
        _node("n7", "因子分析", 1010, 250),
        _node("n8", "因子分析结果", 1240, 190),
        _node("n9", "数据下载", 1010, 360),
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n2"},
        {"id": "e2", "source": "n2", "target": "n3"},
        {"id": "e3", "source": "n2", "target": "n4"},
        {"id": "e4", "source": "n3", "target": "n5", "animated": True},
        {"id": "e5", "source": "n4", "target": "n5"},
        {"id": "e6", "source": "n5", "target": "n6"},
        {"id": "e7", "source": "n5", "target": "n7"},
        {"id": "e8", "source": "n7", "target": "n8"},
        {"id": "e9", "source": "n6", "target": "n8"},
        {"id": "e10", "source": "n5", "target": "n9"},
    ]
    return {"nodes": nodes, "edges": edges}


def _graph_official_05() -> dict[str, Any]:
    nodes = [
        _node("n1", "模型上传", 30, 80),
        _node("n2", "模型上传", 30, 320, node_spec_id="offline.alphagen_upload"),
        _node("n3", "特征工程构建", 260, 80),
        _node("n4", "特征工程构建", 260, 320),
        _node("n5", "Xgboost模型", 500, 80),
        _node("n6", "Xgboost模型", 500, 320),
        _node("n7", "因子构建(机器学习)", 760, 80, node_spec_id="offline.single_model_multi_feature"),
        _node("n8", "因子构建(机器学习)", 760, 320, node_spec_id="offline.single_model_multi_feature"),
        _node("n9", "因子权重组合节点", 980, 200),
        _node("n10", "因子分析", 1200, 120),
        _node("n11", "期货回测", 1200, 300),
        _node("n12", "因子分析结果", 1420, 120),
        _node("n13", "策略回测结果", 1420, 300),
    ]
    edges = [
        {"id": "e1", "source": "n1", "target": "n3"},
        {"id": "e2", "source": "n2", "target": "n4"},
        {"id": "e3", "source": "n3", "target": "n5"},
        {"id": "e4", "source": "n4", "target": "n6"},
        {"id": "e5", "source": "n5", "target": "n7"},
        {"id": "e6", "source": "n6", "target": "n8"},
        {"id": "e7", "source": "n7", "target": "n9"},
        {"id": "e8", "source": "n8", "target": "n9"},
        {"id": "e9", "source": "n9", "target": "n10"},
        {"id": "e10", "source": "n9", "target": "n11"},
        {"id": "e11", "source": "n10", "target": "n12"},
        {"id": "e12", "source": "n11", "target": "n13"},
    ]
    return {"nodes": nodes, "edges": edges}


TEMPLATE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "tpl-official-06",
        "name": "官方案例-6-超参搜索",
        "description": "特征工程 + Optuna + 因子构建 + 因子分析 + 结果输出",
        "tags": ["官方模板", "超参搜索"],
        "updated_at": "2025-12-17 14:15:19",
        "category": "机器学习",
        "official": True,
        "template_group": "官方案例",
        "graph": graph_from_labels(["公式输入", "特征工程构建", "超参数搜索(Optuna)", "因子构建(机器学习)", "因子分析", "因子分析结果"]),
    },
    {
        "id": "tpl-official-04",
        "name": "官方案例-4-稳健策略状态机",
        "description": "状态机识别 + LightGBM + 分层回测。",
        "tags": ["官方模板", "状态识别"],
        "updated_at": "2025-10-15 12:18:44",
        "category": "状态识别",
        "official": True,
        "template_group": "官方案例",
        "graph": graph_from_labels(["公式输入", "特征工程构建", "LightGBM模型", "因子分析", "策略回测结果"]),
    },
    {
        "id": "tpl-official-05",
        "name": "官方案例-5-PPO融合",
        "description": "双路模型融合 + 因子加权组合 + 回测。",
        "tags": ["官方模板", "强化学习"],
        "updated_at": "2025-10-15 12:17:10",
        "category": "强化学习",
        "official": True,
        "template_group": "官方案例",
        "graph": graph_from_labels(["模型上传", "特征工程构建", "Xgboost模型", "因子权重调整", "期货回测", "策略回测结果"]),
    },
    {
        "id": "tpl-official-03",
        "name": "官方案例-3-多因子",
        "description": "多因子合并 + 组合排序 + 回测。",
        "tags": ["官方模板", "多因子"],
        "updated_at": "2025-10-15 12:14:29",
        "category": "因子构建",
        "official": True,
        "template_group": "官方案例",
        "graph": graph_from_labels(["线性因子构建", "非线性因子构建", "多因子合并", "多因子组合", "股票回测", "策略回测结果"]),
    },
    {
        "id": "tpl-official-01",
        "name": "官方案例-1-双均线趋势策略",
        "description": "基于双均线趋势构建基础择时策略。",
        "tags": ["官方模板", "趋势"],
        "updated_at": "2025-10-15 11:18:27",
        "category": "趋势策略",
        "official": True,
        "template_group": "官方案例",
        "graph": graph_from_labels(["公式输入", "因子构建", "股票回测", "策略回测结果"]),
    },
    {
        "id": "tpl-competition-linear-formula",
        "name": "因子大赛-线性因子-公式示例",
        "description": "通过公式快速生成线性因子并完成评估。",
        "tags": ["因子大赛", "线性"],
        "updated_at": "2025-08-18 09:24:36",
        "category": "因子大赛",
        "official": True,
        "template_group": "因子大赛",
        "graph": graph_from_labels(["公式输入", "线性因子构建", "因子分析(期货)", "因子分析结果"]),
    },
    {
        "id": "tpl-competition-linear-python",
        "name": "因子大赛-线性因子-python示例",
        "description": "通过 Python 节点生成线性因子。",
        "tags": ["因子大赛", "python"],
        "updated_at": "2025-08-18 09:24:26",
        "category": "因子大赛",
        "official": True,
        "template_group": "因子大赛",
        "graph": graph_from_labels(["Python代码输入", "线性因子构建", "因子分析(期货)", "因子分析结果"]),
    },
    {
        "id": "tpl-competition-nonlinear-formula",
        "name": "因子大赛-非线性因子-公式示例",
        "description": "非线性公式构建 + 期货回测。",
        "tags": ["因子大赛", "非线性"],
        "updated_at": "2025-08-18 09:22:44",
        "category": "因子大赛",
        "official": True,
        "template_group": "因子大赛",
        "graph": graph_from_labels(["公式输入", "非线性因子构建", "期货回测", "策略回测结果"]),
    },
    {
        "id": "tpl-competition-nonlinear-xgboost",
        "name": "因子大赛-非线性因子-xgboost示例",
        "description": "XGBoost 训练输出非线性因子。",
        "tags": ["因子大赛", "xgboost"],
        "updated_at": "2025-08-18 09:21:06",
        "category": "因子大赛",
        "official": True,
        "template_group": "因子大赛",
        "graph": graph_from_labels(["特征工程构建", "Xgboost模型", "非线性因子构建", "因子分析(期货)", "因子分析结果"]),
    },
    {
        "id": "tpl-competition-optuna-xgboost",
        "name": "因子大赛-非线性因子-超参数搜索xgboost示例",
        "description": "Optuna 搜索 + XGBoost + 非线性因子构建。",
        "tags": ["因子大赛", "超参搜索"],
        "updated_at": "2025-08-18 09:21:06",
        "category": "因子大赛",
        "official": True,
        "template_group": "因子大赛",
        "graph": graph_from_labels(["特征工程构建", "超参数搜索(Optuna)", "Xgboost模型", "非线性因子构建", "因子分析结果"]),
    },
    {
        "id": "tpl-stock-backtest-basic",
        "name": "股票因子回测-基础模板",
        "description": "股票回测标准模板，含策略结果输出。",
        "tags": ["回测", "股票"],
        "updated_at": "2025-08-12 10:10:00",
        "category": "回测模板",
        "official": True,
        "template_group": "回测模板",
        "graph": graph_from_labels(["因子构建", "股票回测", "策略回测结果"]),
    },
    {
        "id": "tpl-future-backtest-basic",
        "name": "期货因子回测-基础模板",
        "description": "期货回测标准模板，含交易成本参数。",
        "tags": ["回测", "期货"],
        "updated_at": "2025-08-12 10:11:00",
        "category": "回测模板",
        "official": True,
        "template_group": "回测模板",
        "graph": graph_from_labels(["因子构建", "期货回测", "策略回测结果"]),
    },
    {
        "id": "tpl-pca-factor-build",
        "name": "PCA因子构建-教学模板",
        "description": "PCA 降维复合因子 + 因子分析。",
        "tags": ["线下课", "PCA"],
        "updated_at": "2025-08-09 09:30:00",
        "category": "线下课专属",
        "official": True,
        "template_group": "线下课专属",
        "graph": graph_from_labels(["特征工程构建", "PCA因子构建", "因子分析", "因子分析结果"]),
    },
]

# 将关键官方模板升级为更接近真实的复杂 DAG
for item in TEMPLATE_CATALOG:
    if item["id"] == "tpl-official-06":
        item["graph"] = _graph_official_06()
    if item["id"] == "tpl-official-05":
        item["graph"] = _graph_official_05()


def _enrich_graph_with_spec(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for node in graph.get("nodes", []):
        label = node.get("label", "")
        spec = NODE_SPEC_BY_NAME.get(label)
        style = node.get("styleVariant")
        if spec:
            style = style or _style_from_category(spec["category"])
            params = {**_default_params(spec["id"]), **(node.get("params") or {})}
            nodes.append(
                {
                    **node,
                    "styleVariant": style,
                    "nodeSpecId": node.get("nodeSpecId") or spec["id"],
                    "params": params,
                }
            )
        else:
            nodes.append({**node, "params": node.get("params") or {}})
    return {"nodes": nodes, "edges": graph.get("edges", [])}


for template in TEMPLATE_CATALOG:
    template["graph"] = _enrich_graph_with_spec(template["graph"])


WORKFLOW_SEED_CATALOG: list[dict[str, Any]] = [
    {
        "id": "wf-001",
        "name": "官方案例-6-超参搜索（运行中）",
        "category": "机器学习",
        "tags": ["官方模板", "超参搜索"],
        "status": "published",
        "updated_at": "2026-03-15 00:32:11",
        "last_run": "2026-03-15 00:35:18",
        "description": "基于官方模板6的实盘前验证流程。",
        "graph": TEMPLATE_CATALOG[0]["graph"],
    },
    {
        "id": "wf-002",
        "name": "因子大赛-非线性因子-超参搜索",
        "category": "因子大赛",
        "tags": ["因子大赛", "xgboost", "optuna"],
        "status": "running",
        "updated_at": "2026-03-14 21:21:09",
        "last_run": "2026-03-14 21:30:44",
        "description": "大赛实验流程，优化非线性因子表现。",
        "graph": TEMPLATE_CATALOG[9]["graph"],
    },
    {
        "id": "wf-003",
        "name": "线下课-PCA因子构建实验",
        "category": "线下课专属",
        "tags": ["PCA", "教学实验"],
        "status": "draft",
        "updated_at": "2026-03-13 18:10:51",
        "last_run": None,
        "description": "教学版工作流，展示 PCA 因子构建完整链路。",
        "graph": TEMPLATE_CATALOG[12]["graph"],
    },
]


REPORT_SEED_PAYLOAD: dict[str, Any] = {
    "metrics": [
        {"label": "IC均值", "value": "0.087", "trend": "up"},
        {"label": "RankIC", "value": "0.104", "trend": "up"},
        {"label": "年化收益", "value": "24.8%", "trend": "up"},
        {"label": "最大回撤", "value": "-7.2%", "trend": "down"},
        {"label": "夏普比率", "value": "1.91", "trend": "up"},
        {"label": "换手率", "value": "0.63", "trend": "down"},
    ],
    "equity_series": [1.0, 1.02, 1.03, 1.01, 1.05, 1.08, 1.06, 1.1, 1.14, 1.12, 1.16, 1.2],
    "layer_return": [
        {"layer": "Q1", "value": -0.03},
        {"layer": "Q2", "value": 0.02},
        {"layer": "Q3", "value": 0.06},
        {"layer": "Q4", "value": 0.11},
        {"layer": "Q5", "value": 0.17},
    ],
    "updated_at": _now_text(),
}
