"""
工单 Agent

功能：判断用户是否需要创建工单，自动提取标题和内容。
"""
import json
from app.services.chat import call_llm
from app.database import get_db


def ticket_agent(state: dict) -> dict:
    """让 LLM 判断要不要建工单，要就提取标题和描述写进 tickets 表"""
    user_message = state["user_message"]
    messages = state["messages"]
    sentiment = state["sentiment"]  # 取出但暂未使用

    # 让 LLM 判断是否需要创建工单，并提取信息
    prompt = f"""分析用户消息，判断是否需要创建工单。
    如果需要，返回JSON：{{"create": true, "title": "工单标题", "content": "问题描述"}}
    如果不需要，返回JSON：{{"create": false}}

    最近对话：
    {chr(10).join([m['content'] for m in messages[-5:]])}
    用户最新消息：{user_message}"""

    result_text = call_llm([{"role": "user", "content": prompt}], max_tokens=200, fallback='{"create": false}',task_type="json_extract")

    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        result = {"create": False}  # 解析失败就当不用建单

    if result.get("create"):
        # 创建工单
        title = result.get("title", "用户反馈")  # 没给标题就用默认值
        content = result.get("content", user_message)
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(  # 写 tickets 表，初始状态 pending
                    "INSERT INTO tickets (user_id, title, content, status) VALUES (%s, %s, %s, 'pending')",
                    (state.get("user_id", 0), title, content),
                )
            db.commit()
        finally:
            db.close()
        response = f"已为您创建工单「{title}」，我们的客服团队会尽快处理。"  # 回复里带上工单标题
    else:
        response = "请问还有什么可以帮您的？如果需要提交工单，请描述您的问题。"  # 不建单就引导用户描述

    return {"response": response, "agent_name": "ticket"}
