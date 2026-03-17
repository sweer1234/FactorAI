from datetime import datetime

from sqlmodel import Session, select

from .models import Report, Run, Template, Workflow


def _dt(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _base_graph():
    return {
        "nodes": [
            {"id": "n1", "label": "行情数据读取", "position": {"x": 40, "y": 120}, "styleVariant": "data"},
            {"id": "n2", "label": "特征工程构建", "position": {"x": 280, "y": 120}, "styleVariant": "feature"},
            {"id": "n3", "label": "XGBoost模型", "position": {"x": 520, "y": 80}, "styleVariant": "model"},
            {"id": "n4", "label": "自定义因子构建", "position": {"x": 760, "y": 120}, "styleVariant": "factor"},
            {"id": "n5", "label": "期货回测", "position": {"x": 1000, "y": 120}, "styleVariant": "backtest"},
        ],
        "edges": [
            {"id": "e1-2", "source": "n1", "target": "n2", "animated": True},
            {"id": "e2-3", "source": "n2", "target": "n3"},
            {"id": "e3-4", "source": "n3", "target": "n4"},
            {"id": "e4-5", "source": "n4", "target": "n5"},
        ],
    }


def seed_if_empty(session: Session) -> None:
    has_data = session.exec(select(Workflow.id)).first()
    if has_data:
        return

    graph = _base_graph()
    workflows = [
        Workflow(
            id="wf-001",
            name="商品期货-多因子增强",
            category="机器学习 + 因子构建",
            tags=["量化交易", "机器学习", "强化学习"],
            status="published",
            updated_at=_dt("2026-03-15 00:32:11"),
            last_run=_dt("2026-03-15 00:35:18"),
            description="用于商品期货主力合约的多因子排序与回测。",
            graph=graph,
        ),
        Workflow(
            id="wf-002",
            name="超参数搜索-稳健性验证",
            category="超参数优化",
            tags=["Optuna", "XGBoost"],
            status="running",
            updated_at=_dt("2026-03-14 21:21:09"),
            last_run=_dt("2026-03-14 21:30:44"),
            description="在滚动窗口下搜索稳健参数组合。",
            graph=graph,
        ),
        Workflow(
            id="wf-003",
            name="期货跨品种择时策略",
            category="回测与组合",
            tags=["CTA", "多因子"],
            status="draft",
            updated_at=_dt("2026-03-13 18:10:51"),
            description="跨品种择时与仓位分配实验。",
            graph={
                "nodes": [
                    {"id": "c1", "label": "行情数据读取", "position": {"x": 40, "y": 120}, "styleVariant": "data"},
                    {"id": "c2", "label": "自定义因子构建", "position": {"x": 280, "y": 120}, "styleVariant": "factor"},
                    {"id": "c3", "label": "期货回测", "position": {"x": 520, "y": 120}, "styleVariant": "backtest"},
                ],
                "edges": [
                    {"id": "ce1", "source": "c1", "target": "c2"},
                    {"id": "ce2", "source": "c2", "target": "c3", "animated": True},
                ],
            },
        ),
    ]

    templates = [
        Template(
            id="tpl-001",
            name="趋势增强模板",
            description="特征工程 + 机器学习训练 + 因子分析 + 回测",
            tags=["官方模板", "趋势"],
            updated_at=_dt("2026-03-10 09:30:14"),
            category="趋势类",
            graph=graph,
        ),
        Template(
            id="tpl-002",
            name="市场状态识别模板",
            description="状态机 + LightGBM + 分层收益对比",
            tags=["官方模板", "状态识别"],
            updated_at=_dt("2026-03-08 17:42:22"),
            category="状态识别",
            graph=graph,
        ),
        Template(
            id="tpl-003",
            name="PCA 复合因子构建",
            description="训练模型提取特征重要度后做 PCA 融合",
            tags=["因子构建", "PCA"],
            updated_at=_dt("2026-03-05 11:06:05"),
            category="复合因子",
            graph={
                "nodes": [
                    {"id": "p1", "label": "特征工程构建", "position": {"x": 60, "y": 120}, "styleVariant": "feature"},
                    {"id": "p2", "label": "XGBoost模型", "position": {"x": 300, "y": 120}, "styleVariant": "model"},
                    {"id": "p3", "label": "PCA因子构建", "position": {"x": 540, "y": 120}, "styleVariant": "factor"},
                    {"id": "p4", "label": "因子分析", "position": {"x": 780, "y": 120}, "styleVariant": "backtest"},
                ],
                "edges": [
                    {"id": "pe1", "source": "p1", "target": "p2"},
                    {"id": "pe2", "source": "p2", "target": "p3"},
                    {"id": "pe3", "source": "p3", "target": "p4", "animated": True},
                ],
            },
        ),
    ]

    runs = [
        Run(
            id="run-901",
            workflow_id="wf-001",
            workflow_name="商品期货-多因子增强",
            status="success",
            duration="01m 43s",
            created_at=_dt("2026-03-15 00:35:18"),
            message="完成 16 个节点，生成回测报告。",
            logs=["[INFO] DAG 编排完成", "[INFO] 因子分析输出完成"],
        ),
        Run(
            id="run-902",
            workflow_id="wf-002",
            workflow_name="超参数搜索-稳健性验证",
            status="running",
            duration="09m 15s",
            created_at=_dt("2026-03-14 21:30:44"),
            message="正在执行参数搜索。",
            logs=["[INFO] 迭代至 trial 42"],
        ),
    ]

    report = Report(
        workflow_id="wf-001",
        workflow_name="商品期货-多因子增强",
        metrics=[
            {"label": "IC均值", "value": "0.087", "trend": "up"},
            {"label": "RankIC", "value": "0.104", "trend": "up"},
            {"label": "年化收益", "value": "24.8%", "trend": "up"},
            {"label": "最大回撤", "value": "-7.2%", "trend": "down"},
            {"label": "夏普比率", "value": "1.91", "trend": "up"},
            {"label": "换手率", "value": "0.63", "trend": "down"},
        ],
        equity_series=[1.0, 1.02, 1.03, 1.01, 1.05, 1.08, 1.06, 1.1, 1.14, 1.12, 1.16, 1.2],
        layer_return=[
            {"layer": "Q1", "value": -0.03},
            {"layer": "Q2", "value": 0.02},
            {"layer": "Q3", "value": 0.06},
            {"layer": "Q4", "value": 0.11},
            {"layer": "Q5", "value": 0.17},
        ],
        updated_at=_dt("2026-03-15 08:00:00"),
    )

    for row in workflows + templates + runs + [report]:
        session.add(row)
    session.commit()
