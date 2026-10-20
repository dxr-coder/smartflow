# SmartFlow 压力测试（Locust）

## 快速开始

```bash
# 安装 Locust
pip install locust

# 启动后端（另一个终端）
cd smartflow
uvicorn app.main:app --port 8000

# 跑压测（场景 1：CRUD 基础设施）
locust -f locust/locustfile.py --host http://localhost:8000 --headless -u 20 -r 2 -t 2m --tags crud

# 跑压测（场景 2：Mock 聊天）
locust -f locust/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 -t 2m --tags chat-mock

# 跑压测（场景 4：健康检查吞吐）
locust -f locust/locustfile.py --host http://localhost:8000 --headless -u 50 -r 5 -t 1m --tags health
```

## 4 个场景说明

| 场景 | tag | 并发建议 | 时长 | 测什么 | 预期瓶颈 |
|------|-----|---------|------|--------|---------|
| CRUD | `crud` | 20-50 | 2min | MySQL+Redis 基础设施 | 连接池（maxconnections=20） |
| Mock 聊天 | `chat-mock` | 10-20 | 2min | 编排开销+缓存命中 | uvicorn 线程池 |
| 真实聊天 | `chat-real` | 3-5 | 1min | 端到端延迟 | LLM API 延迟（5-20s/次） |
| 健康检查 | `health` | 50-100 | 1min | 最轻量端点吞吐上限 | uvicorn 单进程 |

## 结果怎么看

Locust 输出关键指标：
- **RPS**（Requests Per Second）：每秒处理请求数
- **P50/P95/P99**：50%/95%/99% 的请求延迟（P95 = 95% 的请求比这个值快）
- **失败率**：错误请求占比

HTML 报告（可选）：
```bash
locust -f locust/locustfile.py --host http://localhost:8000 \
  --headless -u 20 -r 2 -t 2m --tags crud \
  --html=locust/report-crud.html
```

## 已知限制

1. **没有纯检索端点**：检索只在 chat 流程里（hybrid_search 不是独立 HTTP 接口），所以没有单独的 retrieval 场景。chat-mock 间接覆盖了检索链路。
2. **chat-real 并发必须 ≤5**：真实 LLM 调用每次 5-20s，高并发会打爆 API 配额，且本地 uvicorn 单进程会排队。
3. **单进程瓶颈**：uvicorn 默认 1 worker，Locust 并发再高也会被单进程 GIL 限制。要测多 worker 需 `uvicorn --workers 4`，但内存 job 表会不一致（已知取舍）。
4. **测试账号依赖 seed**：需要先跑 `scripts/seed_demo.py` 创建 dxr/agent01/customer01 账号。
