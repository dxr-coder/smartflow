"""
联网搜索服务

功能：知识库没答案时调 Tavily 搜索网页补充。
"""
import os
import httpx

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def web_search(query: str, max_results: int = 3) -> list[dict]:
    """调 Tavily 搜索，返回 [{title, content, url}]"""
    # 没配 key 就当没这个功能，返回空列表让上层走兜底文案
    if not TAVILY_API_KEY:
        return []
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",  # 快而够用，deep 模式慢一倍
            },
            timeout=10,  # 外部接口，超时别拖死主流程
        )
        data = resp.json()
        # 只留上层用得到的三个字段，丢掉 Tavily 返回的杂项
        return [
            {"title": r["title"], "content": r["content"], "url": r["url"]}
            for r in data.get("results", [])
        ]
    except Exception:
        # 搜索挂了不报错，返回空让对话继续（知识库没命中 + 联网失败 → 建议建工单）
        return []