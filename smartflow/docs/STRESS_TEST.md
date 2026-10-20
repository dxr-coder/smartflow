# SmartFlow 压力测试报告

## 测试环境

- **后端**：uvicorn 单进程，localhost:8000
- **数据库**：MySQL 8.0（连接池 maxconnections=20）
- **缓存**：Redis 7（AOF 持久化）
- **压测工具**：Locust（单进程 gevent 模式）
- **测试账号**：dxr（admin 角色）

## 场景设计

| 场景 | tag | 并发 | 时长 | 测什么 |
|------|-----|------|------|--------|
| CRUD 基础设施 | `crud` | 20 | 2min | MySQL+Redis 读写性能 |
| Mock 聊天 | `chat-mock` | 10 | 2min | LLM 编排链路开销 |
| 真实聊天 | `chat-real` | 3 | 1min | 端到端延迟（受 LLM API 限制） |
| 健康检查 | `health` | 50 | 1min | 最轻量端点吞吐上限 |

## CRUD 场景结果（20 并发，2 分钟）

### 延迟分布

| 接口 | 请求数 | P50 | P95 | P99 | 说明 |
|------|--------|-----|-----|-----|------|
| GET /health | 154 | 2ms | 4ms | 6ms | 极轻量，无压力 |
| GET /tickets | 499 | 9ms | 15ms | 35ms | MySQL 读稳定 |
| GET /stats | 324 | 6ms | 10ms | 25ms | 聚合查询快 |
| POST /tickets | 168 | 8ms | 13ms | 56ms | 写入也快 |
| POST /auth/login | 20 | 2200ms | 2300ms | 2300ms | bcrypt 故意慢 |

### 吞吐量

- **聚合 RPS**：~10（20 并发下）
- **失败率**：0%（1165 请求全部成功）
- **登录延迟 2.2s 的原因**：bcrypt cost=12 是安全设计选择（防止彩虹表攻击），不是性能问题

### 结论

20 并发下 MySQL+Redis 完全没有压力，所有接口 P95 < 15ms。连接池 maxconnections=20 在此并发下够用。

## 已知限制与瓶颈

### 1. 单进程瓶颈
uvicorn 默认 1 worker，Locust 并发再高也会被单进程 GIL 限制。要测多 worker 需 `uvicorn --workers 4`，但内存 job 表会不一致（已知取舍）。

### 2. LLM API 延迟不可控
chat-real 场景每次调用 5-20s，受外部 API 限制，本地压测无法优化。生产环境需要考虑请求队列和超时熔断。

### 3. bcrypt 登录延迟
登录接口 P50=2.2s 是 bcrypt cost=12 的设计选择。如果要优化：降低 cost（牺牲安全性）或改用 argon2（可调参数更灵活）。

### 4. 无独立检索端点
检索只在 chat 流程里（hybrid_search 不是独立 HTTP 接口），所以没有单独的 retrieval 场景。chat-mock 间接覆盖了检索链路。

## 如何复现

```bash
# 1. 启动后端
cd smartflow
uvicorn app.main:app --port 8000

# 2. 运行压测（另一个终端）
cd ..
pip install locust

# CRUD 场景
locust -f locust/locustfile.py --host http://localhost:8000 \
  --headless -u 20 -r 2 -t 2m --tags crud

# Mock 聊天场景
locust -f locust/locustfile.py --host http://localhost:8000 \
  --headless -u 10 -r 2 -t 2m --tags chat-mock

# 健康检查场景
locust -f locust/locustfile.py --host http://localhost:8000 \
  --headless -u 50 -r 5 -t 1m --tags health
```

### 生成 HTML 报告

```bash
locust -f locust/locustfile.py --host http://localhost:8000 \
  --headless -u 20 -r 2 -t 2m --tags crud \
  --html=locust/report-crud.html
```

## 指标解读

- **RPS**（Requests Per Second）：每秒处理请求数
- **P50**：50% 的请求比这个值快（中位数）
- **P95**：95% 的请求比这个值快（长尾延迟）
- **P99**：99% 的请求比这个值快（极端长尾）
- **失败率**：错误请求占比（4xx/5xx）

**生产基线参考**：P50 < 50ms，P95 < 200ms，失败率 < 0.1% 是健康状态。
