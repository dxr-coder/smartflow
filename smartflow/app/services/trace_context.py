"""
链路追踪上下文

功能：用 ContextVar 保存当前请求的 trace_id，
     任意深度的业务代码无需层层传参即可获取，日志自动串成一条链。
数据流：TraceMiddleware.set_trace_id() → 请求链路任意处 get_trace_id()/trace_log()
        → 控制台 JSON 日志自动携带 trace_id
"""
import json
from contextvars import ContextVar

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace_id(trace_id: str):
    """中间件入口调用一次"""
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """任意业务代码取当前请求的 trace_id；不在请求上下文时返回 '-'"""
    return _trace_id_var.get()


def trace_log(stage: str, **fields):
    """
    打一条带 trace_id 的结构化日志。
    用法：trace_log("llm_call", elapsed=1.2, tier="fast")
    """
    entry = {"trace_id": get_trace_id(), "stage": stage, **fields}
    print(json.dumps(entry, ensure_ascii=False))

