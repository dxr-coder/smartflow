"""
聊天路由

功能：定义聊天相关的 HTTP 接口，支持多 Agent 编排 + 伪流式输出。
数据流：
  前端 message → 查缓存 → 拼历史 → 敏感词拦截 → 查询改写
    → invoke_agent 多 Agent 图 → 脱敏 → 落库 → 伪流式吐给前端
"""
import time
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.deps import get_current_user
from app.services.cache import get_cached_answer, set_cached_answer, get_semantic_cached, set_semantic_cached
from app.services.graph import invoke_agent
from app.services.conversation import get_conversation_messages, generate_title, update_conversation_title, save_message
from app.services.query_rewriter import rewrite_query
from app.services.summarizer import maybe_summarize
from app.services.agents.function_agent import set_request
from app.services.masker import mask_sensitive
from app.services.auditor import check_sensitive, log_audit
from app.services.ab_test import get_variant
from app.services.retriever import ab_variant_var


router = APIRouter(prefix="/chat", tags=["聊天"])


@router.get('/stream')
def chat_stream_route(request: Request, message: str, conversation_id: int = None, user=Depends(get_current_user)):
    """聊天主入口：查缓存 → 拼历史 → 调 Agent → 流式返回"""
    try:
        # 1. 精确匹配缓存
        cached = get_cached_answer(message)
        if cached:
            def cached_generator():
                yield f'{{"agent_name":"cache"}}\n'
                yield cached

            return StreamingResponse(cached_generator(), media_type="text/event-stream")  # 格式和正常流一致，前端不用区分

        # 2. 语义缓存
        semantic_answer = get_semantic_cached(message)
        if semantic_answer:
            def semantic_generator():
                yield f'{{"agent_name":"semantic_cache"}}\n'
                yield semantic_answer

            return StreamingResponse(semantic_generator(), media_type="text/event-stream")

        # 3. 构建历史消息（超过阈值自动压缩成摘要）
        history_messages = []
        if conversation_id:
            history = get_conversation_messages(conversation_id, user['user_id'])
            if history:
                raw = [{"role": m["role"], "content": m["content"]} for m in history]  # 只留 role/content
                history_messages = maybe_summarize(conversation_id, raw)

        # 4. 查询改写
        rewrite_result = rewrite_query(message, history_messages)
        rewritten = rewrite_result["rewritten"]  # 后面调 Agent 都用改写后的问法

        # 敏感词拦截
        blocked = check_sensitive(message)
        if blocked:
            log_audit(user['user_id'], 'sensitive_blocked', f'命中敏感词「{blocked}」: {message[:50]}')

            def blocked_gen():
                yield '{"agent_name":"sensitive"}\n'
                yield "您的消息包含敏感内容，已拦截。如有问题请联系管理员。"

            return StreamingResponse(blocked_gen(), media_type="text/event-stream")

        # ab_test：分流结果塞进 ContextVar，检索漏斗 hybrid_search 统一消费（B 组 top_k+2）
        # 已知混淆：答案缓存在这之前命中就直接 return，缓存命中会绕过实验——demo 可接受
        ab_variant_var.set(get_variant(user['user_id']))

        # 5. 调用多 Agent 图（传入改写后的查询）
        set_request(request)  # request 存进 ContextVar，深层 agent 也能取
        result = invoke_agent(history_messages, rewritten)
        response_text = mask_sensitive(result["response"])  # 输出前把敏感信息打码
        agent_name = result["agent_name"]
        # agent 结果挂到 request.state，中间件落库时取走
        request.state.trace_info = {
            "agent_name": agent_name,
            "sentiment": result.get("sentiment"),
            "intent": result.get("intent"),
        }

        # 6. 保存消息
        assistant_msg_id = None
        if conversation_id:
            save_message(conversation_id, 'user', message)  # 用户原话落库
            assistant_msg_id = save_message(conversation_id, "assistant", response_text,
                                            agent_name=agent_name,
                                            source=result.get("source"),
                                            citations=result.get("citations"))

            # 自动生成标题（仅首次对话时）
            try:
                msgs = get_conversation_messages(conversation_id, user['user_id'])
                if msgs is not None and len(msgs) <= 2:
                    title = generate_title(message)
                    update_conversation_title(conversation_id, title)
            except Exception:
                pass  # 标题生成失败不影响对话

        # 7. 缓存（精确 + 语义）
        set_cached_answer(message, response_text)
        set_semantic_cached(message, response_text)

        # 8. 伪流式输出：第一行是 agent_name JSON，后面逐字输出回复
        def stream_response():
            source = result.get("source")
            citations = result.get("citations", [])
            yield json.dumps({"agent_name": agent_name, "message_id": assistant_msg_id, "source": source,
                              "citations": citations}) + "\n"
            for char in response_text:
                yield char
                time.sleep(0.01)  # 每 10ms 吐一个字，模拟打字机

        return StreamingResponse(stream_response(), media_type="text/event-stream")
    except Exception as e:
        print(f"[chat] 请求处理失败: {e}")  # 线上建议换成日志库

        def error_generator():
            yield '{"agent_name":"error"}\n'
            yield "抱歉，系统繁忙，请稍后再试。"

        return StreamingResponse(error_generator(), media_type="text/event-stream")
