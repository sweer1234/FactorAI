from __future__ import annotations

import multiprocessing as mp
import traceback
from typing import Any

import pandas as pd

from ..config import settings


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


def _sandbox_worker(script: str, records: list[dict[str, Any]], queue: mp.Queue, memory_mb: int) -> None:
    try:
        try:
            import resource

            limit_bytes = memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
        except Exception:
            pass

        local_vars: dict[str, Any] = {}
        global_vars: dict[str, Any] = {
            "__builtins__": SAFE_BUILTINS,
            "pd": pd,
        }
        local_vars["df_input"] = pd.DataFrame.from_records(records)

        compiled = compile(script, "<python-node>", "exec")
        exec(compiled, global_vars, local_vars)

        df_factor = local_vars.get("df_factor")
        if not isinstance(df_factor, pd.DataFrame):
            raise ValueError("Python 节点必须输出 df_factor(DataFrame)")
        for required in ["date", "symbol", "factor1"]:
            if required not in df_factor.columns:
                raise ValueError(f"输出缺失字段: {required}")

        queue.put({"ok": True, "records": df_factor.to_dict(orient="records")})
    except Exception as exc:
        queue.put({"ok": False, "error": f"{exc}\n{traceback.format_exc()}"} )


def run_python_node(script: str, df_input: pd.DataFrame, timeout_sec: int | None = None) -> pd.DataFrame:
    timeout = timeout_sec or settings.python_node_timeout
    queue: mp.Queue = mp.Queue()
    process = mp.Process(
        target=_sandbox_worker,
        args=(script, df_input.to_dict(orient="records"), queue, settings.python_node_memory_mb),
        daemon=True,
    )
    process.start()
    process.join(timeout=timeout)

    if process.is_alive():
        process.terminate()
        process.join(1)
        raise TimeoutError(f"Python 节点执行超时（>{timeout}s）")

    if queue.empty():
        raise RuntimeError("Python 节点执行失败：无返回结果")

    result = queue.get_nowait()
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Python 节点未知错误"))

    return pd.DataFrame.from_records(result["records"])
