"""
Locust 压力测试脚本

功能：模拟用户对 SmartFlow 后端发压，测 QPS / P50/P95 延迟 / 错误率
用法：
  pip install locust
  locust -f locust/locustfile.py --host http://localhost:8000 --headless -u 20 -r 2 -t 2m --tags crud
  # -u=并发用户数  -r=每秒启动用户数  -t=持续时间  --tags=只跑带该 tag 的任务

场景设计（单 User 类，用 --tags 过滤任务）：
  crud        登录→查工单→建工单→查统计→健康检查（测 MySQL+Redis）
  chat-mock   登录→聊天（LLM 用 mock，测编排开销+缓存）
  chat-real   登录→聊天（真实 LLM，低并发，测端到端延迟）

数据流：Locust 进程 → HTTP 请求 → uvicorn → FastAPI 路由 → MySQL/Redis/LLM
"""

import random
from locust import HttpUser, task, between, tag


# ========== 测试账号（只用 dxr，其他账号不存在） ==========
CREDENTIALS = [
    {"username": "dxr", "password": "123456"},
]

CHAT_QUESTIONS = [
    "年假有多少天",
    "怎么申请报销",
    "会议室怎么预订",
    "wifi 密码是什么",
    "试用期多久转正",
    "差旅住宿标准是多少",
    "怎么开实习证明",
    "社保什么时候交",
]


class SmartFlowUser(HttpUser):
    """
    单 User 类：所有场景的任务都在这里，用 --tags 控制跑哪些。
    这样 Locust 只启动一个 User 类，不会出现"其他类被 tag 过滤后无任务"的报错。
    """

    wait_time = between(1, 3)

    def on_start(self):
        """每个虚拟用户启动时：登录拿 token"""
        cred = random.choice(CREDENTIALS)
        resp = self.client.post(
            f"/auth/login?username={cred['username']}&password={cred['password']}",
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token", "")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

    # ---- 场景 1: CRUD 基础设施 ----

    @tag("crud")
    @task(3)
    def list_tickets(self):
        self.client.get("/tickets", headers=self.headers, name="/tickets [GET]")

    @tag("crud")
    @task(1)
    def create_ticket(self):
        # 后端用 query 参数接参（不是 JSON body）
        params = {
            "title": f"压测工单-{random.randint(1000, 9999)}",
            "content": "Locust 压测自动创建的工单",
            "category": random.choice(["IT", "HR", "行政", "财务"]),
            "priority": random.choice(["low", "medium", "high"]),
        }
        self.client.post("/tickets", params=params, headers=self.headers, name="/tickets [POST]")

    @tag("crud")
    @task(2)
    def get_stats(self):
        self.client.get("/stats/overview", headers=self.headers, name="/stats [GET]")

    @tag("crud")
    @task(1)
    def health(self):
        self.client.get("/health", name="/health")

    # ---- 场景 2: Mock 聊天 ----

    @tag("chat-mock")
    @task(5)
    def chat_stream_mock(self):
        question = random.choice(CHAT_QUESTIONS)
        self.client.get(
            f"/chat/stream?message={question}",
            headers=self.headers,
            name="/chat/stream [mock]",
        )

    # ---- 场景 3: 真实聊天 ----

    @tag("chat-real")
    @task(5)
    def chat_stream_real(self):
        question = random.choice(CHAT_QUESTIONS)
        self.client.get(
            f"/chat/stream?message={question}",
            headers=self.headers,
            name="/chat/stream [real]",
        )
