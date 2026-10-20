"""
多 Agent 编排

功能：用 LangGraph 定义 Agent 路由图，根据用户意图分发到不同 Agent。
"""
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

from app.services.agents.admin_agent import admin_agent
from app.services.agents.finance_agent import finance_agent
from app.services.agents.hr_agent import hr_agent
from app.services.agents.it_agent import it_agent
from app.services.agents.router import route_intent
from app.services.agents.faq_agent import faq_agent, kb_gate
from app.services.agents.chat_agent import chat_agent
from app.services.agents.ticket_agent import ticket_agent
from app.services.agents.sentiment_agent import sentiment_agent


class AgentState(TypedDict):
    """图的状态"""
    messages: list  # 对话历史
    user_message: str  # 当前用户消息
    intent: str  # 路由判断的意图
    sentiment: str  # 情感分析结果
    response: str  # 最终回复
    agent_name: str  # 处理该请求的 Agent 名称
    context: list  # 检索到的上下文
    source: str  # 回答来源：kb/web/none
    citations: list  # 引用来源
    kb_missed: bool  # 知识库先行是否没接住


def build_graph():
    """构建 Agent 路由图"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("sentiment", sentiment_agent)
    graph.add_node("router", route_intent)
    graph.add_node("faq", faq_agent)
    graph.add_node("chat", chat_agent)
    graph.add_node("ticket", ticket_agent)
    graph.add_node("it", it_agent)
    graph.add_node("hr", hr_agent)
    graph.add_node("finance", finance_agent)
    graph.add_node("admin", admin_agent)
    graph.add_node("kb_gate", kb_gate)

    # 边：入口 → 情感分析 → 知识库先行
    graph.set_entry_point("sentiment")
    graph.add_edge("sentiment", "kb_gate")

    # 知识库没接住才进路由，接住直接结束
    graph.add_conditional_edges(
        "kb_gate",
        lambda s: "router" if s.get("kb_missed") else END,
        {"router": "router", END: END},
    )

    # 路由条件分支
    def decide_next(state):
        intent = state.get("intent", "chat")
        return intent

    graph.add_conditional_edges(
        "router",
        decide_next,
        {
            "it": "it",
            "hr": "hr",
            "finance": "finance",
            "admin": "admin",
            "faq": "faq",
            "chat": "chat",
            "ticket": "ticket",
        },
    )

    # 所有 Agent → END
    graph.add_edge("faq", END)
    graph.add_edge("chat", END)
    graph.add_edge("ticket", END)
    graph.add_edge("it", END)
    graph.add_edge("hr", END)
    graph.add_edge("finance", END)
    graph.add_edge("admin", END)

    return graph.compile()


# 全局单例
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def invoke_agent(messages: list, user_message: str) -> dict:
    """
    调用多 Agent 图。
    返回: {"response": "AI回复", "agent_name": "faq", "sentiment": "neutral"}
    """
    graph = get_graph()
    result = graph.invoke({
        "messages": messages,
        "user_message": user_message,
        "intent": "",
        "sentiment": "",
        "response": "",
        "agent_name": "",
        "context": [],
        "source": "",
        "citations": [],
    })
    return {
        "response": result["response"],
        "agent_name": result["agent_name"],
        "sentiment": result["sentiment"],
        "intent": result.get("intent", ""),
        "source": result.get("source", ""),
        "citations": result.get("citations", []),
    }
