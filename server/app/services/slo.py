from __future__ import annotations

from typing import Any


DEFAULT_THRESHOLDS = {
    "p95_node_duration_ms": 900,
    "failed_nodes": 0,
    "warn_logs": 20,
    "error_logs": 0,
}

PROFILE_THRESHOLDS: dict[str, dict[str, int]] = {
    "default": DEFAULT_THRESHOLDS,
    "ml_relaxed": {"p95_node_duration_ms": 1200, "failed_nodes": 0, "warn_logs": 30, "error_logs": 0},
    "competition": {"p95_node_duration_ms": 1500, "failed_nodes": 0, "warn_logs": 40, "error_logs": 0},
    "backtest_strict": {"p95_node_duration_ms": 800, "failed_nodes": 0, "warn_logs": 15, "error_logs": 0},
    "offline_teaching": {"p95_node_duration_ms": 1800, "failed_nodes": 1, "warn_logs": 60, "error_logs": 0},
}


def resolve_slo_profile(category: str | None, tags: list[str] | None = None, preferred_profile: str | None = None) -> dict[str, Any]:
    tags = tags or []
    if preferred_profile and preferred_profile in PROFILE_THRESHOLDS:
        return {
            "profile": preferred_profile,
            "thresholds": PROFILE_THRESHOLDS[preferred_profile],
            "reason": "manual_profile",
        }

    category_text = (category or "").lower()
    tags_text = ",".join(tags).lower()
    if "回测" in category_text or "backtest" in category_text:
        profile = "backtest_strict"
    elif "机器学习" in category_text or "ml" in category_text:
        profile = "ml_relaxed"
    elif "因子大赛" in category_text or "competition" in tags_text:
        profile = "competition"
    elif "线下课" in category_text or "教学" in tags_text:
        profile = "offline_teaching"
    else:
        profile = "default"

    return {
        "profile": profile,
        "thresholds": PROFILE_THRESHOLDS[profile],
        "reason": "category_auto",
    }
