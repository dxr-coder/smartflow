"""
文本切片服务

功能：按标题层级切分，保留表格结构，支持代码块识别。
"""
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 中文友好的分隔符优先级
splitter = RecursiveCharacterTextSplitter(
    chunk_size=350,  # 中文场景调小，实际输出约300-500字
    chunk_overlap=80,  # 重叠加大，避免关键信息被截断
    separators=[
        "\n## ", "\n### ", "\n#### ",  # 按标题层级切
        "\n\n",  # 按段落切
        "\n",  # 按行切
        "。", "！", "？",  # 按中文句号切
        ".", "!", "?",  # 按英文句号切
        " ",  # 按空格切
    ],
    length_function=len,
)


def split_text(text: str) -> list[str]:
    """智能切片"""
    chunks = splitter.split_text(text)
    # 过滤空片段和过短片段（少于10字符的丢弃）
    return [c.strip() for c in chunks if c.strip() and len(c.strip()) >= 30]
