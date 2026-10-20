"""
工具注册中心

功能：统一管理所有工具（Function Calling），提供注册、查询、执行三个入口。

数据流：
  各工具文件 import 后调用 register_tool() 注册
    → function_agent 调用 get_tools_schema() 获取工具列表传给 LLM
    → LLM 返回 tool_calls 后调用 execute_tool() 执行
    → 执行结果回填给 LLM 生成最终回复
"""
TOOLS = {}  # 工具名 → {"schema": {...}, "func": callable}


def register_tool(name: str, schema: dict, func):
    """
        注册一个工具。
        参数：
            name: 工具名
            schema: {"description": "...", "parameters": {...}}
            func: 执行函数
    """
    TOOLS[name] = {'schema': schema, 'func': func}
    print(f"[tool_registry] 注册工具: {name}")


def get_tools_schema() -> list:
    """
    返回 OpenAI Function Calling 格式的工具列表。
    格式：
    [
        {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}},
        ...
    ]
    """
    schemas = []
    for name, info in TOOLS.items():
        schema = info['schema']
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": schema.get("description", ""),
                "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
            }
        })
    return schemas


def execute_tool(name: str, params: dict) -> dict:
    """
        统一执行入口。
        参数：
            name: 工具名
            params: 工具参数（字典）
        返回：
            成功：工具函数的返回值
            失败：{"error": "错误信息"}
    """
    if name not in TOOLS:
        return {"error": f"未知工具: {name}"}

    func=TOOLS[name]['func']
    try:
        result=func(**params)
        print(f"[tool_registry] 执行成功: {name} → {result}")
        return result
    except Exception as e:
        print(f"[tool_registry] 执行失败: {name} → {e}")
        return {"error": str(e)}
