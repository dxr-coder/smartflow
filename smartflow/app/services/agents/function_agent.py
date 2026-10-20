"""
Function Calling Agent

功能：判断用户问题是否需要调用工具，需要则执行工具并生成回复。

数据流：
  用户消息 → LLM（带工具 schema）
    → 有 tool_calls？
      → 无：直接回复
      → 有：execute_tool → 结果回填 → LLM 生成最终回复
"""

import json
from app.tool_registry import get_tools_schema, execute_tool

# 注册工具（import 时自动执行）
import app.tools  # noqa

from contextvars import ContextVar

_current_request = ContextVar("current_request", default=None)  # 每个请求各一份，互不覆盖


def set_request(request):
    """把当前 request 存进 ContextVar，工具 execute 通过它拿登录用户"""
    _current_request.set(request)   # 不再需要 global


SYSTEM_PROMPT = """你是SmartFlow企业智能服务台助手，服务于IT/HR/行政/财务四个部门。

你可以调用以下工具帮用户完成操作：
- 查询类：查假期余额、查会议室、查报销状态、查设备状态
- 操作类：创建请假申请、预订会议室、提交报销、创建工单

规则：
1. 用户问数据 → 调用查询工具
2. 用户要办事 → 调用操作工具
3. **信息足够就直接调用工具，不要追问确认**
4. 工具执行失败 → 告知原因并建议转人工
5. 无法处理 → 调用 create_ticket 创建工单

例如：
- 用户说"报销9000打车费" → 直接调用 submit_reimbursement(amount=9000, category="travel", description="打车费")
- 用户说"请3天年假" → 直接调用 create_leave_request(leave_type="annual", days=3, ...)
- 缺少必要参数时才追问"""


MAX_TOOL_ROUNDS = 3  # 最多工具调用轮数，防止死循环


def function_agent(state: dict) -> dict:
    """带工具的对话入口：LLM 带着工具 schema 选工具 → 执行 → 结果回填 → LLM 总结"""
    user_message = state["user_message"]
    messages = state["messages"]
    request = _current_request.get()  # 只能读到自己请求那份，A/B 并发各拿各的

    tools_schema = get_tools_schema()  # 注册表里全部工具的 schema，给 LLM 挑选

    # 构建消息
    chat_messages = [{"role": "system", "content": SYSTEM_PROMPT}]  # system 放工具使用规则
    chat_messages.extend(messages[-5:])  # 最近5条历史
    chat_messages.append({"role": "user", "content": user_message})

    # 第一轮：带工具调用
    try:
        completion = call_llm_with_tools(chat_messages, tools_schema)
        message = completion.choices[0].message

        # 检查是否有工具调用
        if not message.tool_calls:
            return {"response": message.content, "agent_name": "function"}  # 模型没要调工具，直接答

        # 执行工具调用
        for _ in range(MAX_TOOL_ROUNDS):
            # 把助手消息（含 tool_calls）加入历史
            chat_messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            # 执行每个工具
            for tc in message.tool_calls:
                tool_name = tc.function.name
                try:
                    tool_params = json.loads(tc.function.arguments)  # LLM给的参数是JSON字符串
                except json.JSONDecodeError:
                    tool_params = {}  # 解析失败就当空参数往下走

                # 注入 request
                if request:
                    tool_params["request"] = request

                # 执行
                tool_result = execute_tool(tool_name, tool_params)  # 真正干活：查库或写库

                # 结果加入历史
                chat_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

            # 再次调用 LLM（不带工具，让 LLM 总结）
            completion = call_llm_with_tools(chat_messages, tools_schema)
            message = completion.choices[0].message

            # 如果没有新的工具调用，返回结果
            if not message.tool_calls:
                return {"response": message.content, "agent_name": "function"}
        # 达到最大轮数
        return {"response": "抱歉，操作未能完成，建议联系人工处理。", "agent_name": "function"}

    except Exception as e:
        print(f"[function_agent] 错误: {e}")  # 打日志方便排查
        return {"response": "抱歉，系统繁忙，请稍后再试。", "agent_name": "function"}  # 对用户只报系统繁忙


def call_llm_with_tools(messages: list, tools: list):
    """带工具的 LLM 调用（走模型路由 smart 档，返回原始 completion）"""
    from app.services.model_router import call_llm_with_tools_router
    return call_llm_with_tools_router(
        messages, tools,
        task_type="function_calling",
        max_tokens=500,
        timeout=15,
    )

