"""
请求链路追踪存储

功能：将每个请求的链路信息写入 MySQL，支持按 trace_id 查询完整链路。
     用于排查慢请求、定位错误、统计 Token 消耗。

数据流：
  middleware.py 生成 trace_id
    → 请求处理过程中各环节更新 trace 信息（agent_name、token 等）
    → 请求结束调用 save_trace() 写入 request_traces 表
    → 排查问题时通过 get_trace(trace_id) 查询完整链路
"""
from app.database import get_db


def save_trace(trace_data: dict):
    """
    保存请求链路记录。

    参数 trace_data 包含：
        trace_id: 链路ID（UUID前12位）
        user_id: 用户ID（可选）
        method: HTTP方法（GET/POST）
        path: 请求路径
        status_code: 响应状态码
        total_time: 总耗时（秒）
        input_tokens: 输入Token数（可选，默认0）
        output_tokens: 输出Token数（可选，默认0）
        agent_name: 处理的Agent名称（可选）
        sentiment: 情感分析结果（可选）
        intent: 路由意图（可选）
        error_msg: 错误信息（可选，正常请求为None）
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """INSERT INTO request_traces
                   (trace_id, user_id, method, path, status_code,
                    total_time, input_tokens, output_tokens,
                    agent_name, sentiment, intent, error_msg)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    trace_data.get("trace_id"),
                    trace_data.get("user_id"),
                    trace_data.get("method"),
                    trace_data.get("path"),
                    trace_data.get("status_code"),
                    trace_data.get("total_time"),
                    trace_data.get("input_tokens", 0),
                    trace_data.get("output_tokens", 0),
                    trace_data.get("agent_name"),
                    trace_data.get("sentiment"),
                    trace_data.get("intent"),
                    trace_data.get("error_msg"),
                ),
            )
        db.commit()
    except Exception as e:
        # 记日志失败不能影响主流程（用户正在等响应），只打印不抛
        print(f"[trace_store] 保存链路记录失败: {e}")
    finally:
        db.close()


def get_trace(trace_id: str) -> dict | None:
    """
    按 trace_id 查询完整链路记录。

    返回：dict（包含全部字段）或 None（未找到）。
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT * FROM request_traces WHERE trace_id = %s",
                (trace_id,),
            )
            return cur.fetchone()  # 没找到返回 None
    finally:
        db.close()


def get_recent_traces(user_id: int = None, limit: int = 50) -> list:
    """
    查询最近的链路记录。

    参数：
        user_id: 按用户筛选（可选，None 则查全部）
        limit: 返回条数，默认 50

    返回：按时间倒序的链路列表。
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            # 传了 user_id 只查这个人的，没传查所有人
            if user_id:
                cur.execute(
                    """SELECT * FROM request_traces
                       WHERE user_id = %s
                       ORDER BY created_at DESC LIMIT %s""",
                    (user_id, limit),
                )
            else:
                cur.execute(
                    "SELECT * FROM request_traces ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            return cur.fetchall()  # 返回字典列表
    finally:
        db.close()
