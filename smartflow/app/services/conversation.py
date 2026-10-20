"""
对话服务

功能：管理用户对话的创建、查询和消息存储。
"""
import json

from app.database import get_db


def create_conversation(user_id: int, title: str = '新对话'):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title) VALUES (%s, %s)",
                (user_id, title)
            )
            db.commit()
            return cur.lastrowid
    finally:
        db.close()


def get_conversations(user_id: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, title, tags, created_at, updated_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC",
                (user_id,)
            )
            return cur.fetchall()
    finally:
        db.close()


def get_conversation_messages(conversation_id, user_id):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("""
                        SELECT m.id, m.role, m.content, m.agent_name, m.source, m.citations
                        FROM messages m
                                 JOIN conversations c ON m.conversation_id = c.id
                        WHERE m.conversation_id = %s
                          AND c.user_id = %s
                        ORDER BY m.created_at
                        """, (conversation_id, user_id))
            rows = cur.fetchall()
            for row in rows:
                if row.get("citations"):
                    row["citations"] = json.loads(row["citations"])
            return rows
    finally:
        db.close()


def save_message(conversation_id, role, content, agent_name=None, source=None, citations=None):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (conversation_id, role, content, agent_name, source, citations) VALUES (%s, %s, %s, %s, %s, %s)",
                (conversation_id, role, content, agent_name, source, json.dumps(citations) if citations else None)
            )
            db.commit()
            return cur.lastrowid
    finally:
        db.close()


def generate_title(first_message: str) -> str:
    """用 LLM 生成对话标题，失败时截取原文前10字"""
    from app.services.chat import call_llm
    title = call_llm(
        [{"role": "user", "content": f"用不超过10个字概括这个对话主题，只输出标题：\n{first_message}"}],
        max_tokens=20,
        fallback=first_message[:10],
        task_type="title"
    )
    title = title.strip().strip('"').strip("'")
    return title if title else first_message[:10]


def update_conversation_title(conversation_id: int, title: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE conversations SET title = %s WHERE id = %s", (title, conversation_id))
        db.commit()
    finally:
        db.close()


def get_conversation_tags(conversation_id: int, user_id: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT tags FROM conversations WHERE id = %s AND user_id = %s",
                (conversation_id, user_id)
            )
            row = cur.fetchone()
            return row["tags"] if row else None
    finally:
        db.close()


def update_conversation_tags(conversation_id: int, user_id: int, tags: str):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET tags = %s WHERE id = %s AND user_id = %s",
                (tags, conversation_id, user_id)
            )
        db.commit()
    finally:
        db.close()
