"""
查询改写服务

功能：将用户口语化问题改写为更适合检索的形式，提取关键词。
"""
import json
from app.services.chat import call_llm


def rewrite_query(user_message: str, history: list = None) -> dict:
    """
    改写用户查询。
    返回: {"rewritten": "改写后的问题", "keywords": ["关键词1", "关键词2"]}
    """
    history_text = ""
    if history:
        history_text = "\n".join([f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content']}" for m in history[-5:]])
    prompt = f"""你是一个查询改写专家。将用户的口语化问题改写为更精确的检索查询。

    规则：
    1. 去掉礼貌用语（你好、请问、谢谢等）
    2. 补充上下文中的隐含指代
    3. 提取 3-5 个核心关键词

    对话历史：
    {history_text}

    用户当前问题：{user_message}

    返回JSON格式：
    {{"rewritten": "改写后的检索查询", "keywords": ["关键词1", "关键词2", "关键词3"]}}"""

    result_text = call_llm([{"role": "user", "content": prompt}], max_tokens=200, fallback=user_message,task_type="rewrite")
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        result = {"rewritten": user_message, "keywords": user_message.split()}

    return result
