from __future__ import annotations

from copy import deepcopy
from typing import Any

import networkx as nx

ERROR_COMPILE_CYCLE = "E_COMPILE_CYCLE"
ERROR_COMPILE_INPUT_UNBOUND = "E_COMPILE_INPUT_UNBOUND"
ERROR_COMPILE_PORT_FAMILY = "E_COMPILE_PORT_FAMILY"
ERROR_COMPILE_PORT_TYPE = "E_COMPILE_PORT_TYPE"
ERROR_COMPILE_SCHEMA_VERSION = "E_COMPILE_SCHEMA_VERSION"
ERROR_COMPILE_SCHEMA_COLUMNS = "E_COMPILE_SCHEMA_COLUMNS"

WARN_COMPILE_PORT_FAMILY = "W_COMPILE_PORT_FAMILY"
WARN_COMPILE_PORT_TYPE = "W_COMPILE_PORT_TYPE"
WARN_COMPILE_INPUT_INFER = "W_COMPILE_INPUT_INFER"
WARN_COMPILE_SCHEMA_VERSION = "W_COMPILE_SCHEMA_VERSION"
WARN_COMPILE_SCHEMA_COLUMNS = "W_COMPILE_SCHEMA_COLUMNS"

PORT_FAMILY_MAP = {
    "dataset": "table",
    "market_df": "table",
    "feature_df": "table",
    "label_df": "table",
    "formula_df": "table",
    "pred_df": "table",
    "pred_a": "table",
    "pred_b": "table",
    "df_factor": "table",
    "factor_pool": "table",
    "weighted_factor": "table",
    "factor_a": "table",
    "factor_b": "table",
    "split_formula_df": "table",
    "converted_formula": "table",
    "industry_feature_df": "table",
    "industry_factor": "table",
    "graph_feature_df": "table",
    "model_obj": "model",
    "alphagen_obj": "model",
    "best_params": "model",
    "backtest_report": "report",
    "analysis_report": "report",
    "result_json": "report",
    "report_json": "report",
    "corr_matrix": "report",
    "ic_report": "report",
    "artifact_url": "artifact",
    "contest_artifact": "artifact",
}

PORT_DATA_TYPE_MAP = {
    "market_df": "market_table",
    "feature_df": "feature_table",
    "label_df": "label_table",
    "formula_df": "formula_table",
    "pred_df": "prediction_table",
    "pred_a": "prediction_table",
    "pred_b": "prediction_table",
    "df_factor": "factor_table",
    "factor_a": "factor_table",
    "factor_b": "factor_table",
    "factor_pool": "factor_pool_table",
    "weighted_factor": "factor_table",
    "dataset": "generic_table",
    "model_obj": "model_binary",
    "alphagen_obj": "model_binary",
    "best_params": "model_param",
    "backtest_report": "report_table",
    "analysis_report": "report_table",
    "result_json": "json_report",
    "report_json": "json_report",
    "corr_matrix": "corr_report",
    "ic_report": "ic_report",
    "artifact_url": "artifact_url",
    "contest_artifact": "artifact_package",
}

# dtype 级 schema 演化规则（版本 -> 必需列）
DTYPE_SCHEMA_EVOLUTION: dict[str, dict[int, list[str]]] = {
    "market_table": {
        1: ["date", "symbol", "close"],
        2: ["date", "symbol", "close", "volume", "ret1", "future_ret"],
    },
    "feature_table": {
        1: ["date", "symbol", "momentum_5", "volatility_10"],
        2: ["date", "symbol", "momentum_5", "volatility_10", "volume_z", "future_ret"],
    },
    "formula_table": {
        1: ["date", "symbol", "formula_value"],
        2: ["date", "symbol", "formula_value", "future_ret"],
    },
    "prediction_table": {
        1: ["date", "symbol", "pred"],
        2: ["date", "symbol", "pred", "future_ret"],
    },
    "factor_table": {
        1: ["date", "symbol", "factor1"],
        2: ["date", "symbol", "factor1", "future_ret"],
    },
    "factor_pool_table": {
        1: ["date", "symbol", "factor_a", "factor_b"],
        2: ["date", "symbol", "factor_a", "factor_b", "future_ret"],
    },
    "corr_report": {1: ["factor", "peer_factor", "corr"]},
}

# 各端口期望的默认 schema 版本
PORT_SCHEMA_VERSION_MAP: dict[str, int] = {
    "market_df": 2,
    "feature_df": 2,
    "formula_df": 2,
    "pred_df": 2,
    "pred_a": 2,
    "pred_b": 2,
    "df_factor": 2,
    "weighted_factor": 2,
    "factor_a": 2,
    "factor_b": 2,
    "factor_pool": 2,
}

PORT_COLUMNS_MAP = {
    "market_df": ["date", "symbol", "close", "volume", "ret1", "future_ret"],
    "feature_df": ["date", "symbol", "momentum_5", "volatility_10", "volume_z", "future_ret"],
    "label_df": ["date", "symbol", "future_ret"],
    "formula_df": ["date", "symbol", "formula_value", "future_ret"],
    "pred_df": ["date", "symbol", "pred", "future_ret"],
    "pred_a": ["date", "symbol", "pred", "future_ret"],
    "pred_b": ["date", "symbol", "pred", "future_ret"],
    "df_factor": ["date", "symbol", "factor1", "future_ret"],
    "factor_a": ["date", "symbol", "factor1", "future_ret"],
    "factor_b": ["date", "symbol", "factor1", "future_ret"],
    "factor_pool": ["date", "symbol", "factor_a", "factor_b", "future_ret"],
    "weighted_factor": ["date", "symbol", "factor1", "future_ret"],
    "corr_matrix": ["factor", "peer_factor", "corr"],
}


def port_family(port: str) -> str:
    return PORT_FAMILY_MAP.get(port, port)


def port_dtype(port: str) -> str:
    return PORT_DATA_TYPE_MAP.get(port, port)


def _schema_required_columns(dtype: str, version: int) -> list[str]:
    rules = DTYPE_SCHEMA_EVOLUTION.get(dtype)
    if not rules:
        return []
    if version in rules:
        return rules[version]
    # 版本不存在时，回落到最大已知版本
    latest = max(rules.keys())
    return rules[latest]


def _schema_version(port: str) -> int:
    return int(PORT_SCHEMA_VERSION_MAP.get(port, 1))


def _base_schema(port: str) -> dict[str, Any]:
    dtype = port_dtype(port)
    version = _schema_version(port)
    default_cols = deepcopy(PORT_COLUMNS_MAP.get(port, []))
    required_cols = _schema_required_columns(dtype, version)
    columns = sorted(set(default_cols) | set(required_cols))
    return {
        "family": port_family(port),
        "dtype": dtype,
        "schema_version": version,
        "required_columns": required_cols,
        "columns": columns,
        "source_port": port,
    }


def _score_schema(expected_port: str, provided_schema: dict[str, Any]) -> int:
    score = 0
    if provided_schema.get("source_port") == expected_port:
        score += 5
    if provided_schema.get("dtype") == port_dtype(expected_port):
        score += 3
    if provided_schema.get("family") == port_family(expected_port):
        score += 1
    return score


def _issue(
    code: str,
    message: str,
    *,
    node_id: str | None = None,
    edge_id: str | None = None,
    detail: dict | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "node_id": node_id,
        "edge_id": edge_id,
        "detail": detail or {},
    }


def _build_fix_suggestions(
    graph: dict[str, Any],
    nodespec_map: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    node_output_schemas: dict[str, dict[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    nodes = graph.get("nodes", [])
    node_map = {node["id"]: node for node in nodes}
    suggestions: list[dict[str, Any]] = []
    exists_keys: set[str] = set()

    for item in issues:
        code = item.get("code")
        node_id = item.get("node_id")
        detail = item.get("detail", {})
        key = f"{code}:{node_id}:{detail.get('input_port')}:{detail.get('edge_id')}"
        if key in exists_keys:
            continue
        exists_keys.add(key)

        if code in {ERROR_COMPILE_INPUT_UNBOUND, WARN_COMPILE_INPUT_INFER} and node_id:
            input_port = detail.get("input_port")
            candidate = None
            for source_id, outputs in node_output_schemas.items():
                for port_name, schema in outputs.items():
                    if _score_schema(str(input_port), schema) > 0:
                        candidate = (source_id, port_name)
                        break
                if candidate:
                    break
            if candidate:
                source_id, source_port = candidate
                suggestions.append(
                    {
                        "issue_code": code,
                        "priority": "high",
                        "title": "补充缺失连线",
                        "message": (
                            f"建议将 {node_map.get(source_id, {}).get('label', source_id)}({source_port}) "
                            f"连到 {node_map.get(node_id, {}).get('label', node_id)}({input_port})"
                        ),
                        "proposed_action": "connect_edge",
                        "patch": {"source": source_id, "target": node_id},
                    }
                )
            else:
                suggestions.append(
                    {
                        "issue_code": code,
                        "priority": "medium",
                        "title": "插入数据准备节点",
                        "message": "未找到可兼容上游，建议在目标节点前插入“特征工程构建/公式输入”作为适配层。",
                        "proposed_action": "insert_adapter_node",
                        "patch": {"target": node_id, "adapter_node_spec_id": "feature.build"},
                    }
                )

        if code in {ERROR_COMPILE_PORT_TYPE, WARN_COMPILE_PORT_TYPE} and node_id:
            suggestions.append(
                {
                    "issue_code": code,
                    "priority": "medium",
                    "title": "调整 schema 版本或插入转换层",
                    "message": "上下游端口类型不匹配，建议：1) 提升上游 schemaVersion；2) 插入转换节点。",
                    "proposed_action": "upgrade_schema_or_insert_transform",
                    "patch": {
                        "target": node_id,
                        "params_patch": {"schemaVersion": detail.get("expected_version")},
                        "adapter_node_spec_id": "feature.build",
                    },
                }
            )

        if code in {ERROR_COMPILE_SCHEMA_VERSION, WARN_COMPILE_SCHEMA_VERSION} and node_id:
            suggestions.append(
                {
                    "issue_code": code,
                    "priority": "high",
                    "title": "升级上游 schema 版本",
                    "message": "上游 schema 版本低于下游需求，建议升级到期望版本。",
                    "proposed_action": "upgrade_schema_version",
                    "patch": {
                        "target": node_id,
                        "params_patch": {"schemaVersion": detail.get("expected_version")},
                    },
                }
            )

        if code in {ERROR_COMPILE_SCHEMA_COLUMNS, WARN_COMPILE_SCHEMA_COLUMNS} and node_id:
            suggestions.append(
                {
                    "issue_code": code,
                    "priority": "medium",
                    "title": "补齐字段映射",
                    "message": "建议在上游或适配节点补齐缺失列（如 future_ret/factor1）。",
                    "proposed_action": "add_column_mapping",
                    "patch": {
                        "target": node_id,
                        "missing_columns": detail.get("missing_columns", []),
                    },
                }
            )

    return suggestions


def compile_workflow_contract(
    graph: dict[str, Any], nodespec_map: dict[str, dict[str, Any]], *, strict: bool = False
) -> dict[str, Any]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    dag = nx.DiGraph()
    for node in nodes:
        dag.add_node(node["id"], label=node.get("label", node["id"]))
    for edge in edges:
        dag.add_edge(edge["source"], edge["target"], edge_id=edge.get("id"))
    if nodes and not nx.is_directed_acyclic_graph(dag):
        return {
            "valid": False,
            "strict": strict,
            "errors": [_issue(ERROR_COMPILE_CYCLE, "工作流图中存在环，无法编译契约")],
            "warnings": [],
            "suggestions": [],
            "node_input_schemas": {},
            "node_output_schemas": {},
        }

    node_map = {node["id"]: node for node in nodes}
    in_edges: dict[str, list[dict[str, Any]]] = {node["id"]: [] for node in nodes}
    for edge in edges:
        in_edges.setdefault(edge["target"], []).append(edge)

    node_input_schemas: dict[str, dict[str, dict[str, Any]]] = {}
    node_output_schemas: dict[str, dict[str, dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    order = list(nx.topological_sort(dag)) if nodes else []
    for node_id in order:
        node_payload = node_map[node_id]
        node_spec_id = node_payload.get("nodeSpecId", "")
        node_spec = nodespec_map.get(node_spec_id, {})
        input_ports = node_spec.get("inputs", [])
        output_ports = node_spec.get("outputs", [])
        node_input_schemas[node_id] = {}

        for input_port in input_ports:
            candidates: list[dict[str, Any]] = []
            for edge in in_edges.get(node_id, []):
                source_id = edge.get("source")
                source_outputs = node_output_schemas.get(source_id, {})
                for source_port, output_schema in source_outputs.items():
                    score = _score_schema(input_port, output_schema)
                    if score > 0:
                        candidates.append(
                            {
                                "score": score,
                                "schema": output_schema,
                                "edge_id": edge.get("id"),
                                "source_port": source_port,
                                "source_id": source_id,
                            }
                        )

            if not candidates:
                issue = _issue(
                    ERROR_COMPILE_INPUT_UNBOUND if strict else WARN_COMPILE_INPUT_INFER,
                    f"{node_payload.get('label', node_id)} 输入端口 {input_port} 未绑定上游输出",
                    node_id=node_id,
                    detail={"input_port": input_port},
                )
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)
                inferred = _base_schema(input_port)
                inferred["inferred"] = True
                node_input_schemas[node_id][input_port] = inferred
                continue

            best = sorted(candidates, key=lambda item: item["score"], reverse=True)[0]
            provided = deepcopy(best["schema"])
            expected = _base_schema(input_port)
            expected_family = expected["family"]
            expected_dtype = expected["dtype"]
            expected_version = int(expected["schema_version"])
            provided_version = int(provided.get("schema_version", 1))

            if provided.get("family") != expected_family:
                issue = _issue(
                    ERROR_COMPILE_PORT_FAMILY if strict else WARN_COMPILE_PORT_FAMILY,
                    (
                        f"{node_payload.get('label', node_id)} 输入 {input_port} 需要家族 {expected_family}，"
                        f"但上游提供 {provided.get('family')}"
                    ),
                    node_id=node_id,
                    edge_id=best.get("edge_id"),
                    detail={
                        "input_port": input_port,
                        "expected_family": expected_family,
                        "provided_family": provided.get("family"),
                        "source_port": best.get("source_port"),
                    },
                )
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)

            if provided.get("dtype") != expected_dtype:
                issue = _issue(
                    ERROR_COMPILE_PORT_TYPE if strict else WARN_COMPILE_PORT_TYPE,
                    (
                        f"{node_payload.get('label', node_id)} 输入 {input_port} 需要类型 {expected_dtype}，"
                        f"但上游提供 {provided.get('dtype')}"
                    ),
                    node_id=node_id,
                    edge_id=best.get("edge_id"),
                    detail={
                        "input_port": input_port,
                        "expected_dtype": expected_dtype,
                        "provided_dtype": provided.get("dtype"),
                        "source_port": best.get("source_port"),
                    },
                )
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)

            if provided_version < expected_version:
                issue = _issue(
                    ERROR_COMPILE_SCHEMA_VERSION if strict else WARN_COMPILE_SCHEMA_VERSION,
                    (
                        f"{node_payload.get('label', node_id)} 输入 {input_port} 期望 schema v{expected_version}，"
                        f"但上游为 v{provided_version}"
                    ),
                    node_id=node_id,
                    edge_id=best.get("edge_id"),
                    detail={
                        "input_port": input_port,
                        "expected_version": expected_version,
                        "provided_version": provided_version,
                        "source_port": best.get("source_port"),
                    },
                )
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)

            provided_cols = set(provided.get("columns", []))
            missing_required = [col for col in expected.get("required_columns", []) if col not in provided_cols]
            if missing_required:
                issue = _issue(
                    ERROR_COMPILE_SCHEMA_COLUMNS if strict else WARN_COMPILE_SCHEMA_COLUMNS,
                    (
                        f"{node_payload.get('label', node_id)} 输入 {input_port} 缺少 schema 必需字段: "
                        f"{missing_required}"
                    ),
                    node_id=node_id,
                    edge_id=best.get("edge_id"),
                    detail={
                        "input_port": input_port,
                        "missing_columns": missing_required,
                        "expected_version": expected_version,
                        "provided_version": provided_version,
                    },
                )
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)

            merged = deepcopy(expected)
            if provided_cols:
                merged["columns"] = sorted(set(merged.get("columns", [])) | provided_cols)
            merged["source_port"] = provided.get("source_port", input_port)
            merged["compatibility"] = "compatible" if provided_version >= expected_version else "backward_compatible"
            node_input_schemas[node_id][input_port] = merged

        node_output_schemas[node_id] = {}
        input_columns_union: set[str] = set()
        input_versions: list[int] = []
        for input_schema in node_input_schemas[node_id].values():
            input_columns_union.update(input_schema.get("columns", []))
            input_versions.append(int(input_schema.get("schema_version", 1)))
        for output_port in output_ports:
            out_schema = _base_schema(output_port)
            out_version = max([int(out_schema.get("schema_version", 1)), *input_versions]) if input_versions else int(
                out_schema.get("schema_version", 1)
            )
            out_schema["schema_version"] = out_version
            out_schema["required_columns"] = _schema_required_columns(out_schema["dtype"], out_version)
            if out_schema["family"] == "table":
                out_schema["columns"] = sorted(
                    set(out_schema.get("columns", []))
                    | input_columns_union
                    | set(out_schema.get("required_columns", []))
                )
                if output_port in {"df_factor", "weighted_factor"}:
                    out_schema["columns"] = sorted(set(out_schema["columns"]) | {"date", "symbol", "factor1"})
            node_output_schemas[node_id][output_port] = out_schema

    all_issues = [*errors, *warnings]
    suggestions = _build_fix_suggestions(graph, nodespec_map, all_issues, node_output_schemas)
    return {
        "valid": len(errors) == 0,
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "node_input_schemas": node_input_schemas,
        "node_output_schemas": node_output_schemas,
    }
