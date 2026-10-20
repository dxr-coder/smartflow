"""
HR 部门 Agent

功能：处理 HR 相关问题（请假/社保/公积金/工资）。
数据流：用户消息 → 判断类型 → 调工具 或 查知识库 → 回复
"""
from app.services.retriever import hybrid_search
from app.services.reranker import rerank
from app.services.chat import call_llm
from app.services.agents.function_agent import function_agent

SYSTEM_PROMPT = """你是SmartFlow HR服务台助手。

你可以帮员工处理：
- 查询假期余额（年假/病假/调休）
- 提交请假申请
- 解答HR制度问题（社保/公积金/薪资/证明）

规则：
1. 查数据/办事 → 调用工具
2. 制度问题 → 基于知识库回答
3. 复杂问题 → 建议创建工单转HRBP"""

# HR 相关的工具关键词
TOOL_KEYWORDS = ["查", "余额", "年假", "病假", "调休", "请假", "申请", "提交", "还剩"]


def hr_agent(state: dict) -> dict:
    """HR入口：命中工具词走 function_agent 调工具，否则查知识库回答"""
    user_message = state["user_message"]

    # 1. 判断是否需要调工具
    if any(kw in user_message for kw in TOOL_KEYWORDS):
        result = function_agent(state)
        if result.get("response"):
            return {"response": result["response"], "agent_name": "hr"}  # 工具链路有结果就直接用

    # 2. 查 HR 知识库
    hits = hybrid_search(user_message, top_k=5, department="hr")  # 只搜HR库，先捞5条
    hits = rerank(user_message, hits, top_k=3)  # rerank 精挑3条
    context = '\n\n'.join([h['content'] for h in hits]) if hits else "暂无相关制度文档，请联系HRBP。"  # 没命中给兜底提示

    chat_messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n参考资料：\n{context}"},  # 知识库内容塞进system
        {"role": "user", "content": user_message}
    ]
    response = call_llm(chat_messages, max_tokens=500, fallback="请联系HRBP获取帮助。")  # 挂了回兜底文案
    return {"response": response, "agent_name": "hr"}
