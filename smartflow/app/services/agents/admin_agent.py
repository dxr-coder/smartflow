"""
行政部门 Agent

功能：处理行政相关问题（会议室/办公用品/访客）。
数据流：用户消息 → 判断类型 → 调工具 或 查知识库 → 回复
"""
from app.services.retriever import hybrid_search
from app.services.reranker import rerank
from app.services.chat import call_llm
from app.services.agents.function_agent import function_agent

SYSTEM_PROMPT = """你是SmartFlow 行政服务台助手。

你可以帮员工处理：
- 查询会议室空闲状态
- 预订会议室
- 解答行政问题（办公用品/访客/停车）

规则：
1. 查会议室/预订 → 调用工具
2. 行政制度 → 基于知识库回答
3. 复杂问题 → 建议创建工单转行政"""

# 行政相关的工具关键词
TOOL_KEYWORDS = ["会议室", "预订", "订", "查", "空闲", "办公用品", "访客"]


def admin_agent(state: dict) -> dict:
    """行政入口：命中工具词走 function_agent 调工具，否则查知识库回答"""
    user_message = state["user_message"]

    # 1. 判断是否需要调工具
    if any(kw in user_message for kw in TOOL_KEYWORDS):
        result = function_agent(state)
        if result.get("response"):
            return {"response": result["response"], "agent_name": "admin"}  # 工具链路有结果就直接用

    # 2. 查行政知识库
    hits = hybrid_search(user_message, top_k=5, department="admin")  # 只搜行政库，先捞5条
    hits = rerank(user_message, hits, top_k=3)  # rerank 精挑3条
    context = '\n\n'.join([h['content'] for h in hits]) if hits else "暂无相关行政制度，请联系行政部门。"  # 没命中给兜底提示

    chat_messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n参考资料：\n{context}"},  # 知识库内容塞进system
        {"role": "user", "content": user_message}
    ]
    response = call_llm(chat_messages, max_tokens=500, fallback="请联系行政部门获取帮助。")  # 挂了回兜底文案
    return {"response": response, "agent_name": "admin"}
