"""
FAQ Agent

功能：检索知识库，基于检索结果回答用户问题。
"""
import time
from app.services.retriever import hybrid_search
from app.services.reranker import rerank
from app.services.chat import call_llm
from app.services.web_search import web_search
from app.services.trace_context import trace_log


def faq_agent(state: dict) -> dict:
    """KB 先行没接住、路由又判成 faq → 直接联网搜"""
    user_message = state["user_message"]
    messages = state["messages"]
    sentiment = state["sentiment"]

    source = "web"
    t0 = time.time()
    web_results = web_search(user_message)
    trace_log("web_search", elapsed=round(time.time() - t0, 2), hits=len(web_results or []))
    if web_results:
        context = '\n\n'.join([f"【{r['title']}】{r['content']}" for r in web_results])
        citations = []
    else:
        source = "none"
        context = "暂无相关资料，建议创建工单联系人工客服。"
        citations = []

    return _answer_with_context(user_message, messages, sentiment, context, citations, source)



def _answer_with_context(user_message, messages, sentiment, context, citations, source):
    """拿到上下文后生成回答：拼 prompt → 调 LLM → 去重引用"""
    # 情感调整语气
    tone_hint = ""
    if sentiment == "negative":
        tone_hint = "用户情绪不满，请用耐心、安抚的语气回答。"
    elif sentiment == "positive":
        tone_hint = "用户态度友好，可以轻松一些。"

    system_prompt = f"""你是SmartFlow AI智能客服。请根据参考资料准确回答用户问题。
    如果参考资料不相关，请如实告知并建议联系人工客服。
    {tone_hint}

    回答要求：
    1. 回答末尾标注引用来源，格式：来源：[1] [2]（只标注实际用到的编号）
    2. 没有参考资料时不标注

    参考资料：
    {context}"""

    chat_messages = [{"role": "system", "content": system_prompt}]
    chat_messages.extend(messages[-10:])
    chat_messages.append({"role": "user", "content": user_message})

    t0 = time.time()
    response = call_llm(chat_messages, max_tokens=4096, fallback="抱歉，知识库暂时无法访问，建议您联系人工客服。")
    trace_log("llm_call", elapsed=round(time.time() - t0, 2), source=source)

    seen_docs = set()
    unique_citations = [c for c in citations if
                        not (c["document_name"] in seen_docs or seen_docs.add(c["document_name"]))]

    return {"response": response, "agent_name": "faq", "source": source,
            "citations": unique_citations, "kb_missed": False}

# 个人数据词 + 办事动作词：这些不查知识库，直接走路由/工具，防止 KB 截胡
DATA_KEYWORDS = ["我的", "还剩", "剩余", "余额", "查一下", "查询", "帮我查", "进度", "到账",
                 "帮我订", "预订", "预约", "帮我申请", "帮我提交", "帮我取消", "帮我创建"]

KB_HIT_THRESHOLD = 0.4  # 真命中实测 0.46+，0.5 会误杀；低于 0.4 基本是不相关


def kb_gate(state: dict) -> dict:
    """知识库先行：命中直接答；没命中打 kb_missed 标记，交给后面的路由"""
    user_message = state["user_message"]
    messages = state["messages"]
    sentiment = state["sentiment"]

    # 强数据词直接放行，不查知识库
    if any(kw in user_message for kw in DATA_KEYWORDS):
        return {"kb_missed": True}

    t0 = time.time()
    hits = hybrid_search(user_message, top_k=10)
    hits = rerank(user_message, hits, top_k=5)
    trace_log("retrieve", elapsed=round(time.time() - t0, 2), hits=len(hits), gate=True)

    if not hits or hits[0].get("rerank_score", 0) < KB_HIT_THRESHOLD:
        return {"kb_missed": True}

    # 命中：拼上下文
    context_parts, citations = [], []
    for i, h in enumerate(hits, 1):
        doc_name = h.get('metadata', {}).get('document_name', '未知文档')
        context_parts.append(f"[{i}] （来源：{doc_name}）\n{h['content']}")
        citations.append({"index": i, "document_name": doc_name})

    return _answer_with_context(user_message, messages, sentiment,
                                '\n\n'.join(context_parts), citations, "kb")
