"""
意图路由 Agent

功能：用 LLM 判断用户意图，决定交给哪个部门/Agent 处理。
路由策略：先区分"知识问答"和"数据查询"，知识问答走 faq（有引用溯源），数据查询走部门 Agent（调工具）。
"""
import time

from app.services.chat import call_llm
from app.services.trace_context import trace_log


def route_intent(state: dict) -> dict:
    """规则优先分流意图，兜底再问 LLM；返回 intent 给下游 agent"""
    user_message = state["user_message"]
    sentiment = state["sentiment"]
    messages = state.get("messages", [])

    recent_context = ""
    if messages:
        recent = messages[-12:]  # 只看最近12条，太老的不管
        recent_context = "\n".join([f"{m['role']}: {m['content']}" for m in recent])  # 拼成文本，给关键词和LLM用

    # ========== 第一步：判断是"知识问答"还是"数据查询" ==========

    # 知识问答特征词：问制度、政策、标准、流程、规定
    knowledge_keywords = [
        "制度", "标准", "规定", "政策", "流程", "要求", "规范",
        "什么是", "是什么", "怎么算", "如何", "哪些", "包括什么",
        "内容", "细则", "条款", "办法",
    ]

    # 数据查询特征词：查个人具体数据（余额、状态、进度）
    data_keywords = [
        "我的", "还剩", "剩余", "余额", "多少", "几天",
        "状态", "进度", "到账", "查一下", "查询", "帮我查",
    ]

    # 部门关键词
    hr_keywords = ["年假", "病假", "调休", "请假", "假期", "社保", "公积金", "工资", "证明", "加班费"]
    it_keywords = ["电脑", "网络", "WiFi", "账号", "密码", "软件", "打印机", "设备", "蓝屏", "死机"]
    finance_keywords = ["报销", "发票", "预算", "费用", "打款", "对公"]
    admin_keywords = ["会议室", "办公用品", "文具", "访客", "停车", "快递"]

    # 判断消息类型
    is_knowledge = any(kw in user_message for kw in knowledge_keywords)
    is_data = any(kw in user_message for kw in data_keywords)

    # ========== 第二步：根据消息类型路由 ==========

    # 规则1：明确的知识问答 → faq（有引用溯源）
    # 例："年假制度是什么"、"报销标准是多少"、"加班费怎么算"
    if is_knowledge and not is_data:
        return {"intent": "faq"}

    # 规则2：数据查询 + 部门关键词 → 部门 Agent（调工具）
    # 例："我的年假还剩几天"、"报销到哪了"、"帮我查WiFi密码重置"
    if is_data or not is_knowledge:
        # 当前消息匹配部门关键词
        if any(kw in user_message for kw in it_keywords):
            return {"intent": "it"}
        if any(kw in user_message for kw in hr_keywords):
            return {"intent": "hr"}
        if any(kw in user_message for kw in finance_keywords):
            return {"intent": "finance"}
        if any(kw in user_message for kw in admin_keywords):
            return {"intent": "admin"}

        # 当前消息没命中，用历史上下文匹配（处理省略说法）
        if any(kw in recent_context for kw in it_keywords):
            return {"intent": "it"}
        if any(kw in recent_context for kw in hr_keywords):
            return {"intent": "hr"}
        if any(kw in recent_context for kw in finance_keywords):
            return {"intent": "finance"}
        if any(kw in recent_context for kw in admin_keywords):
            return {"intent": "admin"}

    # ========== 第三步：LLM 兜底 ==========
    prompt = f"""你是一个意图分类器。根据用户消息和上下文判断属于哪个部门，只回复一个词：
    it - IT设备/网络/账号/软件问题（如：电脑连不上WiFi、软件报错）
    hr - 个人假期/社保/工资查询（如：我的年假还剩几天、工资到账没）
    finance - 个人报销/发票查询（如：我的报销到哪了、发票怎么开）
    admin - 会议室/办公用品/访客（如：帮我订会议室、申请办公用品）
    faq - 制度/政策/流程咨询（如：年假制度是什么、报销标准、加班费怎么算）
    chat - 仅限打招呼/寒暄/感谢/告别
    ticket - 投诉/情绪激动/要求人工

   判断规则：
    - 问"制度/标准/规定/流程/什么是" → faq
    - 查"我的/还剩/多少/余额/状态" + 部门关键词 → 对应部门

    最近对话：
    {recent_context}

    当前消息：{user_message}
    情感倾向：{sentiment}

    只回复一个词："""

    intent = call_llm([{"role": "user", "content": prompt}], max_tokens=500,task_type="intent")  # 规则没分出来，让LLM判

    if intent not in ("it", "hr", "finance", "admin", "faq", "chat", "ticket"):
        intent = "faq"  # LLM答了别的词，统一按知识问答处理

    return {"intent": intent}
