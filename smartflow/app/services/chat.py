"""
聊天服务（LLM 调用）

功能：对外提供 call_llm / chat_stream / get_llm_client 三个入口，签名保持统一，
     内部转发给 model_router 按任务类型分档（fast/smart/backup）并自动 failover。
数据流：Agent → chat.call_llm(task_type=...) → model_router.call_llm_router
        → route() 选档 → 分档 OpenAI client → 失败沿 failover 链切换
"""
from app.services.model_router import (
    call_llm_router,
    chat_stream_router,
    get_client,
)


def get_llm_client():
    """直接拿 OpenAI client 对象（smart 档）"""
    return get_client("smart")


def chat_stream(messages: list, task_type: str = "answer"):
    """流式对话，默认 smart 档；传 task_type="chitchat" 可走 fast 档省成本"""
    yield from chat_stream_router(messages, task_type=task_type)


def call_llm(
    messages: list,
    max_tokens: int = 500,
    fallback: str = None,
    max_retries: int = 2,
    task_type: str = "answer",
) -> str:
    """
    带分档 + 降级的 LLM 调用。

    参数：
        messages: 消息列表 [{"role": "user", "content": "..."}]
        max_tokens: 最大输出 token
        fallback: 降级回复（全部档位失败时返回这个）
        max_retries: 首选档最大重试次数
        task_type: 任务类型（title/intent/faq/function_calling 等，决定走哪档模型）

    返回：
        LLM 回复文本。全部失败且没传 fallback 时返回固定兜底文案。
    """
    # 参数原样转给路由器，选档、重试、failover 都由路由器负责
    return call_llm_router(
        messages,
        task_type=task_type,
        max_tokens=max_tokens,
        fallback=fallback,
        max_retries=max_retries,
    )
