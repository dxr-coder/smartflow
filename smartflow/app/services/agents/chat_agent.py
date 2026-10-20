"""
闲聊 Agent

功能：处理打招呼、闲聊等非业务对话。
"""
from app.services.chat import call_llm


def chat_agent(state: dict) -> dict:
    """闲聊兜底：不调工具，纯 LLM 聊天；负面情绪时把语气放软"""
    user_message = state["user_message"]
    messages = state["messages"]
    sentiment = state["sentiment"]  # 上游 sentiment_agent 算好的情绪标签

    tone_hint = ""
    if sentiment == "negative":
        tone_hint = "用户情绪不佳，请温和回应。"  # 拼进 prompt，让语气柔和点

    system_prompt = f"""你是SmartFlow AI智能客服助手。
用户只是在闲聊，请友好地回应。如果用户有业务需求，引导他说明具体问题。
{tone_hint}"""

    chat_messages = [{"role": "system", "content": system_prompt}]
    chat_messages.extend(messages[-10:])  # 带上最近10条历史，聊起来连贯
    chat_messages.append({"role": "user", "content": user_message})

    response = call_llm(chat_messages, fallback="您好，请问有什么可以帮您？")  # LLM挂了回这句兜底

    return {"response": response, "agent_name": "chat"}
