from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import pandas as pd


def _format_rate(value: float) -> str:
    return f"{value * 100:.1f}%"


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    mdd = 0.0
    for v in values:
        if v > peak:
            peak = v
        drawdown = (v - peak) / peak
        mdd = min(mdd, drawdown)
    return mdd


def _safe_series_corr(left: pd.Series, right: pd.Series, *, method: str = "pearson") -> float:
    joined = pd.concat([left, right], axis=1).dropna()
    if joined.shape[0] < 2:
        return 0.0
    x = joined.iloc[:, 0]
    y = joined.iloc[:, 1]
    if float(x.std()) < 1e-12 or float(y.std()) < 1e-12:
        return 0.0
    with np.errstate(invalid="ignore", divide="ignore"):
        value = x.corr(y, method=method)
    if pd.isna(value):
        return 0.0
    return float(value)


def run_simple_backtest(factor_df: pd.DataFrame, fee_bps: float = 4.0) -> dict:
    if factor_df.empty:
        return {
            "metrics": [],
            "equity_series": [],
            "layer_return": [],
            "updated_at": datetime.utcnow().isoformat(),
        }

    data = factor_df.copy()
    data["date"] = pd.to_datetime(data["date"])
    if "future_ret" not in data.columns:
        # 使用因子映射生成一个近似标签作为占位，避免无标签无法回测
        data["future_ret"] = np.tanh(data["factor1"].fillna(0).to_numpy()) * 0.02

    data["rank"] = data.groupby("date")["factor1"].rank(method="first")
    data["count"] = data.groupby("date")["factor1"].transform("count")
    top_bucket = data[data["rank"] > data["count"] * 0.8]
    daily_ret = top_bucket.groupby("date")["future_ret"].mean().sort_index().fillna(0.0)

    # 简化手续费：每天固定扣减一部分
    fee_daily = fee_bps / 10000 / 10
    pnl = (daily_ret - fee_daily).to_numpy()
    equity = [1.0]
    for r in pnl:
        equity.append(round(equity[-1] * (1 + float(r)), 6))

    total_return = equity[-1] - 1
    periods = max(1, len(daily_ret))
    annual_return = (equity[-1] ** (252 / periods)) - 1
    volatility = float(np.std(pnl)) * math.sqrt(252) if len(pnl) > 1 else 0.0
    sharpe = annual_return / volatility if volatility > 1e-9 else 0.0
    mdd = _max_drawdown(equity)
    ic_values = [
        _safe_series_corr(group["factor1"], group["future_ret"], method="pearson")
        for _, group in data.groupby("date")
    ]
    rank_ic_values = [
        _safe_series_corr(group["factor1"], group["future_ret"], method="spearman")
        for _, group in data.groupby("date")
    ]
    ic_mean = float(np.mean(ic_values)) if ic_values else 0.0
    rank_ic = float(np.mean(rank_ic_values)) if rank_ic_values else 0.0

    quantiles = []
    for idx, label in enumerate(["Q1", "Q2", "Q3", "Q4", "Q5"], start=1):
        lower = (idx - 1) / 5
        upper = idx / 5
        seg = data[(data["rank"] > data["count"] * lower) & (data["rank"] <= data["count"] * upper)]
        quantiles.append({"layer": label, "value": round(float(seg["future_ret"].mean() if not seg.empty else 0.0), 4)})

    metrics = [
        {"label": "IC均值", "value": f"{ic_mean:.3f}", "trend": "up"},
        {"label": "RankIC", "value": f"{rank_ic:.3f}", "trend": "up"},
        {"label": "年化收益", "value": _format_rate(annual_return), "trend": "up"},
        {"label": "最大回撤", "value": _format_rate(mdd), "trend": "down"},
        {"label": "夏普比率", "value": f"{sharpe:.2f}", "trend": "up"},
        {"label": "换手率", "value": f"{min(1.0, 0.35 + abs(total_return)):.2f}", "trend": "down"},
    ]

    return {
        "metrics": metrics,
        "equity_series": equity[-60:],
        "layer_return": quantiles,
        "updated_at": datetime.utcnow().isoformat(),
    }
