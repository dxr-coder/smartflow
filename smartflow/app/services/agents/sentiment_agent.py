"""
情感分析 Agent

功能：分析用户情绪，结果传递给下游 Agent 调整语气。
"""
from app.services.chat import chat_stream
from app.services.chat import call_llm


def sentiment_agent(state: dict) -> dict:
    """对用户消息做情感分类，结果写进 state["sentiment"] 供下游 agent 调语气"""
    user_message = state["user_message"]
    # 只回一个词，好解析又省 token
    prompt = f"""分析以下用户消息的情感倾向，只回复一个词：
        positive（积极/满意）、negative（消极/不满/愤怒）、neutral（中性）
        用户消息：{user_message}"""

    # 用 LLM 做简单情感分类
    sentiment = call_llm([{"role": "user", "content": prompt}], max_tokens=500,task_type="sentiment")  # 走情感专用任务档

    # 标准化
    if sentiment not in ("positive", "negative", "neutral"):
        sentiment = "neutral"  # 模型答了别的词，一律当中性

    return {"sentiment": sentiment}  # 塞进 state，闲聊/FAQ 按它调语气
