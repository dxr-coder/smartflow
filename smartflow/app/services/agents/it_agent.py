"""
IT 部门 Agent

功能：处理 IT 相关问题（设备/网络/账号/软件）。
数据流：用户消息 → 判断类型 → 调工具 或 查知识库 → 回复
"""
from app.services.retriever import hybrid_search
from app.services.reranker import rerank
from app.services.chat import call_llm
from app.services.agents.function_agent import function_agent

SYSTEM_PROMPT = """你是SmartFlow IT服务台助手。

你可以帮员工处理：
- 查询设备状态（电脑/显示器/手机）
- 报修IT故障
- 解答IT问题（网络/账号/软件安装）

规则：
1. 查设备/报修 → 调用工具
2. 技术问题 → 基于知识库回答
3. 复杂问题 → 创建工单转IT支持"""

# IT 相关的工具关键词
TOOL_KEYWORDS = ["查", "设备", "电脑", "型号", "资产", "报修", "状态"]


def it_agent(state: dict) -> dict:
    """IT入口：命中工具词走 function_agent 调工具，否则查知识库回答"""
    user_message = state["user_message"]

    # 1. 判断是否需要调工具
    if any(kw in user_message for kw in TOOL_KEYWORDS):
        result = function_agent(state)
        if result.get("response"):
            return {"response": result["response"], "agent_name": "it"}  # 工具链路有结果就直接用

    # 2. 查 IT 知识库
    hits = hybrid_search(user_message, top_k=5, department="it")  # 只搜IT库，先捞5条
    hits = rerank(user_message, hits, top_k=3)  # rerank 精挑3条
    context = '\n\n'.join([h['content'] for h in hits]) if hits else "暂无相关IT文档，请创建工单联系IT支持。"  # 没命中给兜底提示

    chat_messages = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n参考资料：\n{context}"},  # 知识库内容塞进system
        {"role": "user", "content": user_message}
    ]
    response = call_llm(chat_messages, max_tokens=500, fallback="请创建IT工单获取支持。")  # 挂了回兜底文案
    return {"response": response, "agent_name": "it"}
