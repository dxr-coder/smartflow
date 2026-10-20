"""
Locust 压力测试脚本

功能：模拟多角色用户对 SmartFlow 后端发压，测 QPS / P50/P95 延迟 / 错误率
用法：
  pip install locust
  locust -f locust/locustfile.py --host http://localhost:8000 --headless -u 20 -r 2 -t 2m
  # -u=并发用户数  -r=每秒启动用户数  -t=持续时间  --headless=无界面模式

场景设计（4 个独立场景，用 --tags 过滤）：
  crud        登录→查工单→建工单→查统计（测 MySQL+Redis 基础设施）
  chat-mock   登录→聊天（LLM 用 mock，测编排开销+缓存）
  chat-real   登录→聊天（真实 LLM，低并发，测端到端延迟）
  health      健康检查（测最轻量端点的吞吐上限）

数据流：Locust 进程 → HTTP 请求 → uvicorn → FastAPI 路由 → MySQL/Redis/LLM
"""

import json
import random
import time
from locust import HttpUser, TaskSet, task, between, tag


# ========== 测试账号（seed_demo.py 创建的用户） ==========
# admin 有全部权限；agent 处理工单；customer 提问
CREDENTIALS = [
    {"username": "dxr", "password": "123456"},       # admin
    {"username": "agent01", "password": "123456"},   # agent
    {"username": "customer01", "password": "123456"}, # customer
]

# 聊天测试问题（模拟真实员工提问）
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


class LoginTaskSet(TaskSet):
    """登录任务集：所有场景先登录拿 token"""

    def on_start(self):
        """虚拟用户启动时：随机选一个账号登录"""
        cred = random.choice(CREDENTIALS)
        with self.client.post(
            f"/auth/login?username={cred['username']}&password={cred['password']}",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token", "")
                self.headers = {"Authorization": f"Bearer {self.token}"}
                resp.success()
            else:
                self.token = ""
                self.headers = {}
                resp.failure(f"登录失败: {resp.status_code}")


class CrudTasks(LoginTaskSet):
    """场景 1：CRUD 基础设施（测 MySQL + Redis）"""

    @tag("crud")
    @task(3)
    def list_tickets(self):
        """查工单列表（GET，读 MySQL）"""
        self.client.get("/tickets", headers=self.headers, name="/tickets [GET]")

    @tag("crud")
    @task(1)
    def create_ticket(self):
        """建工单（POST，写 MySQL）"""
        payload = {
            "title": f"压测工单-{random.randint(1000, 9999)}",
            "content": "Locust 压测自动创建的工单",
            "department": random.choice(["IT", "HR", "行政", "财务"]),
            "priority": random.choice(["low", "medium", "high"]),
        }
        self.client.post(
            "/tickets",
            json=payload,
            headers=self.headers,
            name="/tickets [POST]",
        )

    @tag("crud")
    @task(2)
    def get_stats(self):
        """查统计（聚合查询，读多张表）"""
        self.client.get("/stats/overview", headers=self.headers, name="/stats [GET]")

    @tag("crud")
    @task(1)
    def get_health(self):
        """健康检查（最轻量端点）"""
        self.client.get("/health", name="/health [GET]")


class ChatMockTasks(LoginTaskSet):
    """场景 2：聊天（mock LLM，测编排开销 + 缓存命中率）"""

    @tag("chat-mock")
    @task(5)
    def chat_stream(self):
        """聊天流式接口（SSE）——mock 模式下 LLM 秒回，测的是编排链路开销"""
        question = random.choice(CHAT_QUESTIONS)
        self.client.get(
            f"/chat/stream?message={question}",
            headers=self.headers,
            name="/chat/stream [mock]",
        )


class ChatRealTasks(LoginTaskSet):
    """场景 3：聊天（真实 LLM，低并发，测端到端延迟）"""

    @tag("chat-real")
    @task(5)
    def chat_stream_real(self):
        """真实 LLM 调用——每次 5-20s，只适合低并发（≤5）"""
        question = random.choice(CHAT_QUESTIONS)
        self.client.get(
            f"/chat/stream?message={question}",
            headers=self.headers,
            name="/chat/stream [real]",
        )


class HealthTasks(HttpUser):
    """场景 4：纯健康检查（不登录，测最轻量端点的吞吐上限）"""

    # 不需要等登录，直接发
    wait_time = between(0.1, 0.5)
    weight = 1  # 低权重，避免刷屏

    @tag("health")
    @task(1)
    def health(self):
        self.client.get("/health", name="/health")


# ========== 用户类注册 ==========
# 每个场景一个 User 类，用 --tags 控制跑哪个
# 默认（不加 --tags）：所有场景混合跑

class CrudUser(CrudTasks):
    """CRUD 场景用户"""
    wait_time = between(1, 3)   # 每个请求间隔 1-3s（模拟真实用户）
    weight = 3


class ChatMockUser(ChatMockTasks):
    """Mock 聊天场景用户"""
    wait_time = between(2, 5)
    weight = 2


class ChatRealUser(ChatRealTasks):
    """真实 LLM 场景用户"""
    wait_time = between(3, 8)   # LLM 慢，给更长的等待时间
    weight = 1
