"""
工具包

功能：自动扫描本目录下所有工具文件并注册到 tool_registry。
新增工具只需在本目录创建 .py 文件，定义 SCHEMA 和 execute，无需改本文件。
"""
import importlib
import pkgutil
from app.tool_registry import register_tool


def auto_register_tools():
    """扫描当前包下所有模块，发现 SCHEMA + execute 就自动注册"""
    package = importlib.import_module(__name__)  # 拿到本包，才能枚举目录下的模块
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):  # 遍历 tools 目录所有 .py
        if module_name.startswith("_"):
            continue  # 跳过 __init__ 这类私有文件
        try:
            mod = importlib.import_module(f"{__name__}.{module_name}")
        except Exception as e:
            print(f"[tools] 加载 {module_name} 失败: {e}")  # 单个文件坏了不拖垮整个包
            continue

        schema = getattr(mod, "SCHEMA", None)  # 模块里有没有 SCHEMA
        func = getattr(mod, "execute", None)  # 有没有 execute 执行函数
        if schema and callable(func):
            register_tool(module_name, schema, func)  # 按文件名注册进全局工具表


auto_register_tools()  # import 本包即完成注册，function_agent 直接可用
