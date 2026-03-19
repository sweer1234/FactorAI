from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .backtest import run_simple_backtest
from .sandbox import run_python_node


@dataclass
class RunContext:
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    report: dict[str, Any] | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)


PORT_FRAME_ALIASES: dict[str, list[str]] = {
    "market_df": ["market_df"],
    "feature_df": ["feature_df"],
    "label_df": ["label_df"],
    "formula_df": ["formula_df", "feature_df"],
    "df_factor": ["factor_df", "weighted_factor", "combined_factor"],
    "factor_pool": ["factor_pool"],
    "weighted_factor": ["weighted_factor", "factor_df"],
    "pred_df": ["pred_df"],
    "pred_a": ["pred_a", "pred_df"],
    "pred_b": ["pred_b", "pred_df"],
    "corr_matrix": ["corr_matrix"],
    "analysis_report": ["analysis_report"],
    "backtest_report": ["backtest_report"],
}

PORT_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "market_df": {"date", "symbol", "close"},
    "feature_df": {"date", "symbol"},
    "label_df": {"date", "symbol"},
    "df_factor": {"date", "symbol", "factor1"},
    "factor_pool": {"date", "symbol"},
    "pred_df": {"date", "symbol"},
}

MODEL_PORTS = {"model_obj", "alphagen_obj", "best_params"}
ARTIFACT_PORTS = {"artifact_url", "contest_artifact"}


def _generate_market_data(lookback: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(20260315)
    symbols = ["AU", "CU", "AG", "RB", "AL", "ZN"]
    dates = pd.bdate_range(end=pd.Timestamp.utcnow().normalize(), periods=max(80, int(lookback)))
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        price = 100 + float(rng.normal(0, 1))
        for date in dates:
            drift = rng.normal(0.0006, 0.012)
            price = max(1.0, price * (1 + drift))
            rows.append(
                {
                    "date": date.strftime("%Y-%m-%d"),
                    "symbol": symbol,
                    "close": round(price, 4),
                    "volume": float(max(1000, rng.normal(10000, 1200))),
                }
            )
    return pd.DataFrame(rows)


def _ensure_factor_df(ctx: RunContext) -> pd.DataFrame:
    for key in ["factor_df", "weighted_factor", "combined_factor"]:
        value = ctx.frames.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return value
    handle_factor_custom(ctx, params={})
    return ctx.frames["factor_df"]


def _ensure_future_ret(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "future_ret" not in out.columns:
        out["future_ret"] = np.tanh(out["factor1"].fillna(0.0).to_numpy()) * 0.01
    return out


def _rank_zscore(values: pd.Series) -> pd.Series:
    if values.empty:
        return values
    std = float(values.std())
    if std < 1e-9:
        return pd.Series(np.zeros(len(values)), index=values.index)
    return (values - values.mean()) / std


def _validate_node_inputs(
    node_name: str, node_spec: dict[str, Any] | None, params: dict[str, Any], ctx: RunContext
) -> list[dict[str, Any]]:
    if not node_spec:
        return []
    strict = bool(params.get("strict_inputs") or params.get("strictInputs") or False)
    warnings: list[dict[str, Any]] = []
    missing: list[str] = []

    for port in node_spec.get("inputs", []):
        if port in MODEL_PORTS:
            model_exists = any(key in ctx.frames for key in ["model_obj", "best_params"]) or any(
                key in ctx.artifacts for key in ["model", "alphagen"]
            )
            if not model_exists:
                missing.append(port)
            continue
        if port in ARTIFACT_PORTS:
            if not ctx.artifacts:
                missing.append(port)
            continue

        aliases = PORT_FRAME_ALIASES.get(port, [port])
        frame = next((ctx.frames.get(key) for key in aliases if isinstance(ctx.frames.get(key), pd.DataFrame)), None)
        if frame is None:
            missing.append(port)
            continue

        required_cols = PORT_REQUIRED_COLUMNS.get(port, set())
        if required_cols and not required_cols.issubset(set(frame.columns)):
            detail = f"{node_name} 输入 {port} 缺少字段 {sorted(required_cols - set(frame.columns))}"
            if strict:
                raise ValueError(f"E_NODE_INPUT_SCHEMA: {detail}")
            warnings.append({"code": "W_NODE_INPUT_SCHEMA", "message": detail})

    if missing:
        detail = f"{node_name} 缺失输入端口: {', '.join(missing)}"
        if strict:
            raise ValueError(f"E_NODE_INPUT_MISSING: {detail}")
        warnings.append({"code": "W_NODE_INPUT_MISSING", "message": f"{detail}，已尝试降级执行"})
    return warnings


def handle_market_data(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    lookback = (params or {}).get("lookback", 180)
    market_df = _generate_market_data(lookback=lookback)
    market_df["ret1"] = market_df.groupby("symbol")["close"].pct_change().fillna(0.0)
    market_df["future_ret"] = market_df.groupby("symbol")["ret1"].shift(-1).fillna(0.0)
    ctx.frames["market_df"] = market_df
    ctx.log(f"[INFO] 行情读取完成: {len(market_df)} 行")


def handle_feature_engineering(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    market_df = ctx.frames.get("market_df")
    if market_df is None:
        handle_market_data(ctx, params={})
        market_df = ctx.frames["market_df"]

    df = market_df.copy()
    df["momentum_5"] = df.groupby("symbol")["close"].pct_change(5).fillna(0.0)
    df["volatility_10"] = (
        df.groupby("symbol")["ret1"].rolling(10, min_periods=2).std().reset_index(level=0, drop=True).fillna(0.0)
    )
    df["volume_z"] = (
        df.groupby("symbol")["volume"].transform(lambda x: (x - x.mean()) / (x.std() + 1e-6)).fillna(0.0)
    )
    if (params or {}).get("normalize", True):
        scale_cols = ["momentum_5", "volatility_10", "volume_z"]
        scaler = StandardScaler()
        df[scale_cols] = scaler.fit_transform(df[scale_cols].to_numpy())
    ctx.frames["feature_df"] = df[["date", "symbol", "momentum_5", "volatility_10", "volume_z", "future_ret"]]
    ctx.frames["label_df"] = df[["date", "symbol", "future_ret"]]
    ctx.frames["formula_df"] = ctx.frames["feature_df"].copy()
    ctx.log("[INFO] 特征工程完成")


def handle_model(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    feature_df = ctx.frames.get("feature_df")
    if feature_df is None:
        handle_feature_engineering(ctx, params={})
        feature_df = ctx.frames["feature_df"]

    x = feature_df[["momentum_5", "volatility_10", "volume_z"]].to_numpy()
    y = feature_df["future_ret"].to_numpy()
    x = StandardScaler().fit_transform(x)
    eta = float((params or {}).get("eta", (params or {}).get("learningRate", 0.05)))
    max_depth = float((params or {}).get("max_depth", (params or {}).get("maxDepth", 6)))
    model_shift = float((params or {}).get("modelShift", 0.0))
    weights = np.array([0.45 + eta * 0.2, -0.3 + 0.01 * max_depth, 0.25 + model_shift], dtype=float)
    pred = x @ weights
    pred_df = feature_df[["date", "symbol"]].copy()
    pred_df["pred"] = pred
    pred_df["future_ret"] = y
    ctx.frames["pred_df"] = pred_df
    ctx.frames["pred_a"] = pred_df.copy()
    pred_b = pred_df.copy()
    pred_b["pred"] = pred_b["pred"].rolling(5, min_periods=1).mean()
    ctx.frames["pred_b"] = pred_b
    ctx.frames["feature_importance"] = pd.DataFrame(
        {"feature": ["momentum_5", "volatility_10", "volume_z"], "importance": np.abs(weights)}
    )
    ctx.frames["model_obj"] = pd.DataFrame([{"algo": "linear-sim", "eta": eta, "max_depth": max_depth}])
    ctx.log("[INFO] 模型节点完成")


def handle_optuna_search(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    trials = int((params or {}).get("trials", 50))
    best_eta = round(0.02 + min(0.3, trials / 1000), 4)
    best_depth = min(12, 4 + max(1, trials // 20))
    ctx.frames["best_params"] = pd.DataFrame([{"eta": best_eta, "max_depth": best_depth, "trials": trials}])
    tuned_params = {**(params or {}), "eta": best_eta, "max_depth": best_depth}
    handle_model(ctx, params=tuned_params)
    ctx.log(f"[INFO] 超参搜索完成: eta={best_eta}, max_depth={best_depth}")


def handle_factor_custom(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    pred_df = ctx.frames.get("pred_df")
    if pred_df is None:
        handle_model(ctx, params={})
        pred_df = ctx.frames["pred_df"]
    factor_name = str((params or {}).get("factorName", "factor1"))
    factor_df = pred_df[["date", "symbol", "future_ret"]].copy()
    factor_df[factor_name] = pred_df["pred"].to_numpy()
    if factor_name != "factor1":
        factor_df["factor1"] = factor_df[factor_name]
    ctx.frames["factor_df"] = factor_df[["date", "symbol", "factor1", "future_ret"]]
    ctx.log("[INFO] 自定义因子构建完成")


def handle_factor_pca(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    feature_df = ctx.frames.get("feature_df")
    if feature_df is None:
        handle_feature_engineering(ctx, params={})
        feature_df = ctx.frames["feature_df"]
    x = feature_df[["momentum_5", "volatility_10", "volume_z"]].to_numpy()
    x = StandardScaler().fit_transform(x)
    components = int((params or {}).get("components", 1))
    pca = PCA(n_components=max(1, min(components, x.shape[1])), random_state=42)
    score = pca.fit_transform(x)[:, 0]
    factor_df = feature_df[["date", "symbol", "future_ret"]].copy()
    factor_df["factor1"] = score
    ctx.frames["factor_df"] = factor_df
    ctx.log("[INFO] PCA 因子构建完成")


def handle_factor_merge(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    base = _ensure_factor_df(ctx)
    left = base[["date", "symbol", "factor1", "future_ret"]].rename(columns={"factor1": "factor_a"})
    right = base[["date", "symbol", "factor1"]].copy()
    right["factor1"] = right["factor1"].rolling(7, min_periods=1).mean()
    right = right.rename(columns={"factor1": "factor_b"})
    join_type = str((params or {}).get("join_type", "inner"))
    merged = left.merge(right, on=["date", "symbol"], how="inner" if join_type == "inner" else "left")
    merged["factor_b"] = merged["factor_b"].fillna(0.0)
    ctx.frames["factor_pool"] = merged
    ctx.log(f"[INFO] 多因子合并完成({join_type})")


def handle_factor_weight_adjust(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    pool = ctx.frames.get("factor_pool")
    if pool is None:
        handle_factor_merge(ctx, params={})
        pool = ctx.frames["factor_pool"]
    factor_cols = [col for col in pool.columns if col.startswith("factor_")]
    if not factor_cols:
        pool = pool.copy()
        pool["factor_a"] = pool.get("factor1", 0.0)
        factor_cols = ["factor_a"]
    method = str((params or {}).get("method", "ic_weight"))
    if method == "equal":
        weights = np.ones(len(factor_cols)) / max(1, len(factor_cols))
    else:
        scores = []
        for col in factor_cols:
            val = float(pool[col].corr(pool["future_ret"])) if "future_ret" in pool.columns else 0.0
            scores.append(abs(val))
        arr = np.array(scores, dtype=float)
        if float(arr.sum()) < 1e-9:
            weights = np.ones(len(factor_cols)) / max(1, len(factor_cols))
        else:
            weights = arr / arr.sum()
    weighted = pool[["date", "symbol"]].copy()
    weighted["factor1"] = (pool[factor_cols].to_numpy() @ weights).astype(float)
    weighted["future_ret"] = pool["future_ret"] if "future_ret" in pool.columns else 0.0
    ctx.frames["weighted_factor"] = weighted
    ctx.frames["factor_df"] = weighted
    ctx.log("[INFO] 因子权重调整完成")


def handle_factor_combine(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    pool = ctx.frames.get("factor_pool")
    if pool is None:
        handle_factor_merge(ctx, params={})
        pool = ctx.frames["factor_pool"]
    factor_cols = [col for col in pool.columns if col.startswith("factor_")]
    if not factor_cols:
        handle_factor_weight_adjust(ctx, params={})
        return
    mode = str((params or {}).get("combine_mode", "rank_sum"))
    df = pool[["date", "symbol", "future_ret"]].copy() if "future_ret" in pool.columns else pool[["date", "symbol"]].copy()
    values = pool[factor_cols].copy()
    if mode == "zscore_sum":
        z = values.apply(_rank_zscore)
        df["factor1"] = z.sum(axis=1)
    else:
        rank = values.rank(axis=0, pct=True)
        df["factor1"] = rank.sum(axis=1)
    if "future_ret" not in df.columns:
        df["future_ret"] = np.tanh(df["factor1"].fillna(0.0).to_numpy()) * 0.01
    ctx.frames["combined_factor"] = df[["date", "symbol", "factor1", "future_ret"]]
    ctx.frames["factor_df"] = ctx.frames["combined_factor"]
    ctx.log(f"[INFO] 多因子组合完成({mode})")


def handle_factor_corr_analysis(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    pool = ctx.frames.get("factor_pool")
    if pool is None:
        handle_factor_merge(ctx, params={})
        pool = ctx.frames["factor_pool"]
    factor_cols = [col for col in pool.columns if col.startswith("factor_")]
    if not factor_cols:
        handle_factor_weight_adjust(ctx, params={})
        pool = ctx.frames.get("factor_pool", pool)
        factor_cols = [col for col in pool.columns if col.startswith("factor_")]
    method = str((params or {}).get("corr_method", "spearman"))
    corr = pool[factor_cols].corr(method="spearman" if method == "spearman" else "pearson")
    corr = corr.reset_index().rename(columns={"index": "factor"})
    ctx.frames["corr_matrix"] = corr
    ctx.log(f"[INFO] 因子相关性分析完成({method})")


def handle_factor_corr_result(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    corr = ctx.frames.get("corr_matrix")
    if corr is None:
        handle_factor_corr_analysis(ctx, params={})
        corr = ctx.frames["corr_matrix"]
    threshold = float((params or {}).get("threshold", 0.8))
    melted = corr.melt(id_vars=["factor"], var_name="peer_factor", value_name="corr").dropna()
    filtered = melted[melted["factor"] != melted["peer_factor"]]
    filtered["abs_corr"] = filtered["corr"].abs()
    result = filtered[filtered["abs_corr"] >= threshold].sort_values("abs_corr", ascending=False).head(20)
    ctx.frames["report_json"] = result
    ctx.log(f"[INFO] 因子相关性结果输出完成(threshold={threshold})")


def handle_multi_ml_blend(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    pred_a = ctx.frames.get("pred_a")
    pred_b = ctx.frames.get("pred_b")
    if pred_a is None or pred_b is None:
        handle_model(ctx, params={})
        pred_a = ctx.frames["pred_a"]
        pred_b = ctx.frames["pred_b"]
    mode = str((params or {}).get("blend_mode", "rank_avg"))
    merged = pred_a[["date", "symbol", "pred", "future_ret"]].rename(columns={"pred": "pred_a"}).merge(
        pred_b[["date", "symbol", "pred"]].rename(columns={"pred": "pred_b"}),
        on=["date", "symbol"],
        how="inner",
    )
    if mode == "avg":
        factor = (merged["pred_a"] + merged["pred_b"]) / 2
    else:
        rank_a = merged["pred_a"].rank(pct=True)
        rank_b = merged["pred_b"].rank(pct=True)
        factor = (rank_a + rank_b) / 2
    factor_df = merged[["date", "symbol", "future_ret"]].copy()
    factor_df["factor1"] = factor.to_numpy()
    ctx.frames["factor_df"] = factor_df
    ctx.log(f"[INFO] 多模型融合完成({mode})")


def handle_weight_combo(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    handle_factor_weight_adjust(ctx, params=params)
    rebalance_days = int((params or {}).get("rebalance_days", 5))
    weighted = ctx.frames["weighted_factor"].copy()
    weighted["factor1"] = weighted["factor1"].rolling(max(1, rebalance_days), min_periods=1).mean()
    ctx.frames["weighted_factor"] = weighted
    ctx.frames["factor_df"] = weighted
    ctx.log(f"[INFO] 动态权重组合完成(rebalance_days={rebalance_days})")


def handle_python_node(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    base_df = ctx.frames.get("feature_df")
    if base_df is None:
        handle_feature_engineering(ctx, params={})
        base_df = ctx.frames["feature_df"]
    source = base_df[["date", "symbol", "future_ret"]].copy()
    source["factor1"] = source["future_ret"].rolling(3, min_periods=1).mean().fillna(0.0)
    script = (params or {}).get(
        "script",
        "df_factor = df_input[['date','symbol']].copy()\n"
        "df_factor['factor1'] = (df_input['factor1'] * 0.7).fillna(0.0)\n",
    )
    timeout = int((params or {}).get("timeout", 6))
    result = run_python_node(script, source, timeout_sec=timeout)
    merged = result.merge(source[["date", "symbol", "future_ret"]], on=["date", "symbol"], how="left")
    merged["future_ret"] = merged["future_ret"].fillna(0.0)
    ctx.frames["factor_df"] = merged[["date", "symbol", "factor1", "future_ret"]]
    ctx.log("[INFO] Python 节点执行完成")


def handle_upload_node(ctx: RunContext, params: dict[str, Any] | None = None, kind: str = "model") -> None:
    path = (
        (params or {}).get("artifactPath")
        or (params or {}).get("path")
        or (params or {}).get("artifact_path")
        or "unknown"
    )
    artifact_id = (params or {}).get("artifactId")
    ctx.artifacts[kind] = {"path": path, "artifact_id": artifact_id, "loaded": True}
    if kind in {"model", "alphagen"}:
        ctx.frames["model_obj"] = pd.DataFrame(
            [{"name": f"{kind}-artifact", "path": str(path), "artifact_id": artifact_id or ""}]
        )
    ctx.log(f"[INFO] 上传节点完成，已载入 {kind} 资源: {path}")


def handle_download_node(ctx: RunContext, params: dict[str, Any] | None = None, kind: str = "data") -> None:
    file_type = (params or {}).get("file_type") or (params or {}).get("format") or "csv"
    artifact_url = f"/downloads/{kind}-{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}.{file_type}"
    ctx.artifacts[f"{kind}_download"] = {"file_type": file_type, "success": True, "artifact_url": artifact_url}
    ctx.log(f"[INFO] 下载节点完成，导出类型: {file_type}")


def handle_backtest(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    factor_df = _ensure_factor_df(ctx)
    fee_bps = float((params or {}).get("fee_bps", (params or {}).get("feeBps", 4.0)))
    factor_df = _ensure_future_ret(factor_df)
    ctx.report = run_simple_backtest(factor_df, fee_bps=fee_bps)
    ctx.frames["backtest_report"] = pd.DataFrame(ctx.report.get("metrics", []))
    ctx.log("[INFO] 回测执行完成")


def handle_passthrough(ctx: RunContext, node_name: str) -> None:
    handle_feature_engineering(ctx, params={})
    ctx.log(f"[WARN] 节点 {node_name} 使用通用执行逻辑")


HANDLER_BY_SPEC_ID = {
    "data.market": handle_market_data,
    "basic.formula": handle_feature_engineering,
    "feature.build": handle_feature_engineering,
    "ml.xgboost": handle_model,
    "ml.lightgbm": handle_model,
    "ml.optuna": handle_optuna_search,
    "ml.mlp": handle_model,
    "ml.svm": handle_model,
    "ml.gru": handle_model,
    "ml.lstm": handle_model,
    "ml.cnn": handle_model,
    "ml.gnn": handle_model,
    "ml.random_forest": handle_model,
    "ml.transformer": handle_model,
    "factor.custom": handle_factor_custom,
    "factor.custom_build": handle_factor_custom,
    "factor.linear_build": handle_factor_custom,
    "factor.nonlinear_build": handle_factor_custom,
    "factor.combine": handle_factor_combine,
    "factor.weight_adjust": handle_factor_weight_adjust,
    "factor.merge": handle_factor_merge,
    "factor.corr_analysis": handle_factor_corr_analysis,
    "factor.corr_result": handle_factor_corr_result,
    "factor.pca": handle_factor_pca,
    "offline.pca": handle_factor_pca,
    "offline.spearman": handle_factor_pca,
    "offline.multi_ml": handle_multi_ml_blend,
    "offline.weight_combo": handle_weight_combo,
    "basic.python": handle_python_node,
    "basic.model_upload": lambda ctx, params=None: handle_upload_node(ctx, params=params, kind="model"),
    "offline.alphagen_upload": lambda ctx, params=None: handle_upload_node(ctx, params=params, kind="alphagen"),
    "basic.model_download": lambda ctx, params=None: handle_download_node(ctx, params=params, kind="model"),
    "basic.data_download": lambda ctx, params=None: handle_download_node(ctx, params=params, kind="data"),
    "backtest.future": handle_backtest,
    "backtest.stock": handle_backtest,
    "factor.analysis_future": handle_backtest,
    "factor.analysis": handle_backtest,
    "factor.analysis_result": handle_backtest,
    "backtest.strategy_result": handle_backtest,
}


def execute_node(node: dict[str, Any], node_spec: dict[str, Any] | None, ctx: RunContext) -> list[dict[str, Any]]:
    node_name = node.get("label", node.get("id", "node"))
    node_spec_id = node.get("nodeSpecId") or (node_spec or {}).get("id")
    params = node.get("params") or {}
    warnings = _validate_node_inputs(str(node_name), node_spec, params, ctx)
    handler = HANDLER_BY_SPEC_ID.get(node_spec_id)
    if handler:
        handler(ctx, params=params)
        return warnings

    lowered = str(node_name).lower()
    if "python" in lowered:
        handle_python_node(ctx, params=params)
    elif "行情" in str(node_name):
        handle_market_data(ctx, params=params)
    elif "回测" in str(node_name) or "分析结果" in str(node_name) or "因子分析" in str(node_name):
        handle_backtest(ctx, params=params)
    elif "pca" in lowered or "spearman" in lowered:
        handle_factor_pca(ctx, params=params)
    elif "公式" in str(node_name):
        handle_feature_engineering(ctx, params=params)
    elif "特征" in str(node_name):
        handle_feature_engineering(ctx, params=params)
    elif "xgboost" in lowered or "lightgbm" in lowered or "模型" in str(node_name) or "超参数" in str(node_name):
        handle_model(ctx, params=params)
    elif "因子" in str(node_name):
        handle_factor_custom(ctx, params=params)
    else:
        handle_passthrough(ctx, str(node_name))
    return warnings
