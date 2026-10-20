"""
对话摘要服务
功能：对话超过 N 轮时，把旧对话压缩成摘要，节省 token。
"""
from app.services.chat import call_llm
from app.database import get_db

SUMMARIZE_THRESHOLD = 20
RECENT_KEEP = 6

def maybe_summarize(conversation_id: int, messages: list) -> list:
    if len(messages) <= SUMMARIZE_THRESHOLD:
        return messages

    old_messages = messages[:-RECENT_KEEP]
    recent_messages = messages[-RECENT_KEEP:]

    cached = _get_cached_summary(conversation_id, len(old_messages))
    if cached:
        return [{"role": "user", "content": f"[系统提示] 以下是之前的对话摘要，供参考：\n{cached}"}] + recent_messages

    conversation_text = "\n".join(f"{m['role']}: {m['content']}" for m in old_messages)
    summary = call_llm(
        [{"role": "user", "content": f"用200字以内概括这段对话的要点：\n\n{conversation_text}"}],
        max_tokens=150,
        fallback="用户进行了多轮对话。",
        task_type="summarize"
    )
    _save_summary(conversation_id, summary, len(old_messages))
    return [{"role": "user", "content": f"[系统提示] 以下是之前的对话摘要，供参考：\n{summary}"}] + recent_messages

def _get_cached_summary(conversation_id: int, old_count: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT conversation_summary, summary_msg_count FROM conversations WHERE id = %s", (conversation_id,))
            row = cur.fetchone()
            if row and row["conversation_summary"] and (row["summary_msg_count"] or 0) >= old_count:
                return row["conversation_summary"]
            return None
    finally:
        db.close()

def _save_summary(conversation_id: int, summary: str, msg_count: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE conversations SET conversation_summary = %s, summary_msg_count = %s WHERE id = %s",
                        (summary, msg_count, conversation_id))
        db.commit()
    finally:
        db.close()
