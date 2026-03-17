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
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(message)


def _generate_market_data(lookback: int = 180) -> pd.DataFrame:
    rng = np.random.default_rng(20260315)
    symbols = ["AU", "CU", "AG", "RB", "AL", "ZN"]
    dates = pd.bdate_range(end=pd.Timestamp.utcnow().normalize(), periods=max(80, lookback))
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


def handle_market_data(ctx: RunContext) -> None:
    market_df = _generate_market_data()
    market_df["ret1"] = market_df.groupby("symbol")["close"].pct_change().fillna(0.0)
    market_df["future_ret"] = market_df.groupby("symbol")["ret1"].shift(-1).fillna(0.0)
    ctx.frames["market_df"] = market_df
    ctx.log(f"[INFO] 行情读取完成: {len(market_df)} 行")


def handle_feature_engineering(ctx: RunContext) -> None:
    market_df = ctx.frames.get("market_df")
    if market_df is None:
        handle_market_data(ctx)
        market_df = ctx.frames["market_df"]

    df = market_df.copy()
    df["momentum_5"] = df.groupby("symbol")["close"].pct_change(5).fillna(0.0)
    df["volatility_10"] = (
        df.groupby("symbol")["ret1"].rolling(10, min_periods=2).std().reset_index(level=0, drop=True).fillna(0.0)
    )
    df["volume_z"] = (
        df.groupby("symbol")["volume"].transform(lambda x: (x - x.mean()) / (x.std() + 1e-6)).fillna(0.0)
    )
    ctx.frames["feature_df"] = df[["date", "symbol", "momentum_5", "volatility_10", "volume_z", "future_ret"]]
    ctx.log("[INFO] 特征工程完成")


def handle_model(ctx: RunContext) -> None:
    feature_df = ctx.frames.get("feature_df")
    if feature_df is None:
        handle_feature_engineering(ctx)
        feature_df = ctx.frames["feature_df"]

    x = feature_df[["momentum_5", "volatility_10", "volume_z"]].to_numpy()
    y = feature_df["future_ret"].to_numpy()
    x = StandardScaler().fit_transform(x)
    # 简化模型推理：用线性加权模拟预测得分
    weights = np.array([0.45, -0.3, 0.25], dtype=float)
    pred = x @ weights
    pred_df = feature_df[["date", "symbol"]].copy()
    pred_df["pred"] = pred
    pred_df["future_ret"] = y
    ctx.frames["pred_df"] = pred_df
    ctx.frames["feature_importance"] = pd.DataFrame(
        {"feature": ["momentum_5", "volatility_10", "volume_z"], "importance": np.abs(weights)}
    )
    ctx.log("[INFO] 模型节点完成")


def handle_factor_custom(ctx: RunContext) -> None:
    pred_df = ctx.frames.get("pred_df")
    if pred_df is None:
        handle_model(ctx)
        pred_df = ctx.frames["pred_df"]
    factor_df = pred_df[["date", "symbol", "future_ret"]].copy()
    factor_df["factor1"] = pred_df["pred"].to_numpy()
    ctx.frames["factor_df"] = factor_df
    ctx.log("[INFO] 自定义因子构建完成")


def handle_factor_pca(ctx: RunContext) -> None:
    feature_df = ctx.frames.get("feature_df")
    if feature_df is None:
        handle_feature_engineering(ctx)
        feature_df = ctx.frames["feature_df"]
    x = feature_df[["momentum_5", "volatility_10", "volume_z"]].to_numpy()
    x = StandardScaler().fit_transform(x)
    pca = PCA(n_components=1, random_state=42)
    score = pca.fit_transform(x)[:, 0]
    factor_df = feature_df[["date", "symbol", "future_ret"]].copy()
    factor_df["factor1"] = score
    ctx.frames["factor_df"] = factor_df
    ctx.log("[INFO] PCA 因子构建完成")


def handle_python_node(ctx: RunContext, script: str | None = None) -> None:
    base_df = ctx.frames.get("feature_df")
    if base_df is None:
        handle_feature_engineering(ctx)
        base_df = ctx.frames["feature_df"]
    source = base_df[["date", "symbol", "future_ret"]].copy()
    source["factor1"] = source["future_ret"].rolling(3, min_periods=1).mean().fillna(0.0)
    python_script = script or (
        "df_factor = df_input[['date','symbol']].copy()\n"
        "df_factor['factor1'] = (df_input['factor1'] * 0.7).fillna(0.0)\n"
    )
    result = run_python_node(python_script, source)
    merged = result.merge(source[["date", "symbol", "future_ret"]], on=["date", "symbol"], how="left")
    merged["future_ret"] = merged["future_ret"].fillna(0.0)
    ctx.frames["factor_df"] = merged[["date", "symbol", "factor1", "future_ret"]]
    ctx.log("[INFO] Python 节点执行完成")


def handle_backtest(ctx: RunContext) -> None:
    factor_df = ctx.frames.get("factor_df")
    if factor_df is None:
        handle_factor_custom(ctx)
        factor_df = ctx.frames["factor_df"]
    ctx.report = run_simple_backtest(factor_df, fee_bps=4.0)
    ctx.log("[INFO] 回测执行完成")


def execute_node_by_label(label: str, ctx: RunContext) -> None:
    name = label.lower()
    if "python" in name:
        handle_python_node(ctx)
    elif "行情" in label:
        handle_market_data(ctx)
    elif "回测" in label or "分析结果" in label or "因子分析" in label:
        handle_backtest(ctx)
    elif "pca" in name or "spearman" in name:
        handle_factor_pca(ctx)
    elif "公式" in label:
        handle_feature_engineering(ctx)
    elif "特征" in label:
        handle_feature_engineering(ctx)
    elif "xgboost" in name or "lightgbm" in name or "模型" in label or "超参数" in label:
        handle_model(ctx)
    elif "因子" in label:
        handle_factor_custom(ctx)
    else:
        # 未识别节点默认透传为特征处理，确保流程可运行
        handle_feature_engineering(ctx)
        ctx.log(f"[WARN] 未识别节点 {label}，已按特征节点处理")
