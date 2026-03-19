from __future__ import annotations

from copy import deepcopy
from typing import Any

import networkx as nx

ERROR_COMPILE_CYCLE = "E_COMPILE_CYCLE"
ERROR_COMPILE_INPUT_UNBOUND = "E_COMPILE_INPUT_UNBOUND"
ERROR_COMPILE_PORT_FAMILY = "E_COMPILE_PORT_FAMILY"
ERROR_COMPILE_PORT_TYPE = "E_COMPILE_PORT_TYPE"

WARN_COMPILE_PORT_FAMILY = "W_COMPILE_PORT_FAMILY"
WARN_COMPILE_PORT_TYPE = "W_COMPILE_PORT_TYPE"
WARN_COMPILE_INPUT_INFER = "W_COMPILE_INPUT_INFER"

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


def _base_schema(port: str) -> dict[str, Any]:
    return {
        "family": port_family(port),
        "dtype": port_dtype(port),
        "columns": deepcopy(PORT_COLUMNS_MAP.get(port, [])),
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
            "errors": [{"code": ERROR_COMPILE_CYCLE, "message": "工作流图中存在环，无法编译契约"}],
            "warnings": [],
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
                for _, output_schema in source_outputs.items():
                    score = _score_schema(input_port, output_schema)
                    if score > 0:
                        candidates.append({"score": score, "schema": output_schema, "edge_id": edge.get("id")})

            if not candidates:
                issue = {
                    "code": ERROR_COMPILE_INPUT_UNBOUND if strict else WARN_COMPILE_INPUT_INFER,
                    "message": f"{node_payload.get('label', node_id)} 输入端口 {input_port} 未绑定上游输出",
                    "node_id": node_id,
                    "detail": {"input_port": input_port},
                }
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
            expected_family = port_family(input_port)
            expected_dtype = port_dtype(input_port)
            if provided.get("family") != expected_family:
                issue = {
                    "code": ERROR_COMPILE_PORT_FAMILY if strict else WARN_COMPILE_PORT_FAMILY,
                    "message": (
                        f"{node_payload.get('label', node_id)} 输入 {input_port} 需要家族 {expected_family}，"
                        f"但上游提供 {provided.get('family')}"
                    ),
                    "node_id": node_id,
                    "edge_id": best.get("edge_id"),
                    "detail": {"input_port": input_port, "provided": provided},
                }
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)

            if provided.get("dtype") != expected_dtype:
                issue = {
                    "code": ERROR_COMPILE_PORT_TYPE if strict else WARN_COMPILE_PORT_TYPE,
                    "message": (
                        f"{node_payload.get('label', node_id)} 输入 {input_port} 需要类型 {expected_dtype}，"
                        f"但上游提供 {provided.get('dtype')}"
                    ),
                    "node_id": node_id,
                    "edge_id": best.get("edge_id"),
                    "detail": {"input_port": input_port, "provided": provided},
                }
                if strict:
                    errors.append(issue)
                else:
                    warnings.append(issue)

            merged = _base_schema(input_port)
            provided_cols = provided.get("columns", [])
            if provided_cols:
                merged["columns"] = sorted(set(merged.get("columns", [])) | set(provided_cols))
            merged["source_port"] = provided.get("source_port", input_port)
            node_input_schemas[node_id][input_port] = merged

        node_output_schemas[node_id] = {}
        input_columns_union: set[str] = set()
        for input_schema in node_input_schemas[node_id].values():
            input_columns_union.update(input_schema.get("columns", []))
        for output_port in output_ports:
            out_schema = _base_schema(output_port)
            if out_schema["family"] == "table":
                out_schema["columns"] = sorted(set(out_schema.get("columns", [])) | input_columns_union)
                if output_port in {"df_factor", "weighted_factor"}:
                    out_schema["columns"] = sorted(set(out_schema["columns"]) | {"date", "symbol", "factor1"})
            node_output_schemas[node_id][output_port] = out_schema

    return {
        "valid": len(errors) == 0,
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "node_input_schemas": node_input_schemas,
        "node_output_schemas": node_output_schemas,
    }
