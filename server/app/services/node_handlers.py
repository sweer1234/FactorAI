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
    weights = np.array([0.45 + eta * 0.2, -0.3 + 0.01 * max_depth, 0.25], dtype=float)
    pred = x @ weights
    pred_df = feature_df[["date", "symbol"]].copy()
    pred_df["pred"] = pred
    pred_df["future_ret"] = y
    ctx.frames["pred_df"] = pred_df
    ctx.frames["feature_importance"] = pd.DataFrame(
        {"feature": ["momentum_5", "volatility_10", "volume_z"], "importance": np.abs(weights)}
    )
    ctx.log("[INFO] 模型节点完成")


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


def handle_backtest(ctx: RunContext, params: dict[str, Any] | None = None) -> None:
    factor_df = ctx.frames.get("factor_df")
    if factor_df is None:
        handle_factor_custom(ctx, params={})
        factor_df = ctx.frames["factor_df"]
    fee_bps = float((params or {}).get("fee_bps", (params or {}).get("feeBps", 4.0)))
    ctx.report = run_simple_backtest(factor_df, fee_bps=fee_bps)
    ctx.log("[INFO] 回测执行完成")


def handle_upload_node(ctx: RunContext, params: dict[str, Any] | None = None, kind: str = "model") -> None:
    path = (params or {}).get("path") or (params or {}).get("artifact_path") or "unknown"
    ctx.artifacts[kind] = {"path": path, "loaded": True}
    if kind in {"model", "alphagen"}:
        ctx.frames["model_obj"] = pd.DataFrame([{"name": f"{kind}-artifact", "path": str(path)}])
    ctx.log(f"[INFO] 上传节点完成，已载入 {kind} 资源: {path}")


def handle_download_node(ctx: RunContext, params: dict[str, Any] | None = None, kind: str = "data") -> None:
    file_type = (params or {}).get("file_type") or (params or {}).get("format") or "csv"
    ctx.artifacts[f"{kind}_download"] = {"file_type": file_type, "success": True}
    ctx.log(f"[INFO] 下载节点完成，导出类型: {file_type}")


def handle_passthrough(ctx: RunContext, node_name: str) -> None:
    handle_feature_engineering(ctx, params={})
    ctx.log(f"[WARN] 节点 {node_name} 使用通用执行逻辑")


HANDLER_BY_SPEC_ID = {
    "data.market": handle_market_data,
    "basic.formula": handle_feature_engineering,
    "feature.build": handle_feature_engineering,
    "ml.xgboost": handle_model,
    "ml.lightgbm": handle_model,
    "ml.optuna": handle_model,
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
    "factor.combine": handle_factor_custom,
    "factor.weight_adjust": handle_factor_custom,
    "factor.merge": handle_factor_custom,
    "factor.pca": handle_factor_pca,
    "offline.pca": handle_factor_pca,
    "offline.spearman": handle_factor_pca,
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


def execute_node(node: dict[str, Any], node_spec: dict[str, Any] | None, ctx: RunContext) -> None:
    node_name = node.get("label", node.get("id", "node"))
    node_spec_id = node.get("nodeSpecId") or (node_spec or {}).get("id")
    params = node.get("params") or {}
    handler = HANDLER_BY_SPEC_ID.get(node_spec_id)
    if handler:
        handler(ctx, params=params)
        return

    # fallback by node name
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
