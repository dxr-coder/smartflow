"""
财务部门 Agent

功能：处理财务相关问题（报销/发票/预算）。
数据流：用户消息 → 判断类型 → 调工具 或 查知识库 → 回复
"""
from app.services.retriever import hybrid_search
from app.services.reranker import rerank
from app.services.chat import call_llm
from app.services.agents.function_agent import function_agent

SYSTEM_PROMPT = """你是SmartFlow 财务服务台助手。

你可以帮员工处理：
- 查询报销单状态
- 提交报销申请
- 解答财务制度问题（报销标准/发票要求/预算）

规则：
1. 查报销/提交报销 → 调用工具
2. 制度问题 → 基于知识库回答
3. 复杂问题 → 建议创建工单转财务"""

# 财务相关的工具关键词
TOOL_KEYWORDS = ["报销", "查", "发票", "金额", "提交", "申请", "到账", "状态"]


def finance_agent(state: dict) -> dict:
    """财务入口：命中工具词走 function_agent 调工具，否则查知识库回答"""
    user_message = state["user_message"]

    # 1. 检测到报销相关，直接走 function_agent（让 LLM 决定调工具还是追问）
    if any(kw in user_message for kw in TOOL_KEYWORDS):
        result = function_agent(state)
        if result.get("response"):
            return {"response": result["response"], "agent_name": "finance"}  # 工具链路有结果就直接用

    # 2. 查财务知识库
    hits = hybrid_search(user_message, top_k=5, department="finance")  # 只搜财务库，先捞5条
    hits = rerank(user_message, hits, top_k=3)  # rerank 精挑3条
    context = '\n\n'.join([h['content'] for h in hits]) if hits else "暂无相关财务制度，请联系财务部门。"  # 没命中给兜底提示

    chat_messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n参考资料：\n{context}"},  # 知识库内容塞进system
        {"role": "user", "content": user_message}
    ]
    response = call_llm(chat_messages, max_tokens=500, fallback="请联系财务部门获取帮助。")  # 挂了回兜底文案
    return {"response": response, "agent_name": "finance"}
