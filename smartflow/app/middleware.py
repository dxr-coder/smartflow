"""
可观测性中间件

功能：每个请求自动生成 trace_id，双写注入（request.state + ContextVar 全局链路），
     响应头回传 X-Trace-ID，请求结束（成功或异常）结构化日志写 MySQL + 控制台。
数据流：
  请求进来 → 生成 trace_id → request.state + ContextVar
    → 各环节 get_trace_id() / trace_log() 任意深度可取
    → 请求结束 → 写 request_traces 表 + 控制台 JSON（异常路径也记）
"""
import json
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.background import BackgroundTask
from fastapi.responses import JSONResponse
from app.services.rate_limiter import check_rate_limit
from app.services.auth import decode_token
from app.services.trace_context import set_trace_id

SLOW_THRESHOLD = 2.0  # 超过 2 秒标记慢请求


class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 1. 生成 trace_id，双写：request.state（HTTP 层用）+ ContextVar（深层业务用）
        trace_id = str(uuid.uuid4())[:12]
        request.state.trace_id = trace_id
        request.state.start_time = time.time()
        set_trace_id(trace_id)

        # ===== 限流检查=====
        auth_header = request.headers.get("Authorization")
        if auth_header:
            try:
                payload = decode_token(auth_header.replace("Bearer ", ""))
                user_id = payload["user_id"]
                from app.database import get_db
                db = get_db()
                try:
                    with db.cursor() as cur:
                        cur.execute(
                            "SELECT r.name as role FROM users u JOIN roles r ON u.role_id = r.id WHERE u.id = %s",
                            (user_id,)
                        )
                        row = cur.fetchone()
                        role = row["role"] if row else "user"
                finally:
                    db.close()

                limit_result = check_rate_limit(user_id, role)
                if not limit_result["allowed"]:
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "请求过于频繁，请稍后再试"},
                        headers={"X-RateLimit-Remaining": "0", "X-Trace-ID": trace_id},
                    )
                request.state.rate_remaining = limit_result["remaining"]
            except Exception:
                pass  # token 解析失败就跳过限流，让 auth 依赖去报错

        # 2. 执行请求 —— 异常也必须记 trace（失败请求最需要排查）
        # 字段名要对齐 request_traces 表：status_code / total_time / error_msg
        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = round(time.time() - request.state.start_time, 3)
            log_entry = {
                "trace_id": trace_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "total_time": elapsed,
                "user_id": getattr(request.state, "user_id", None),
                "error_msg": str(e)[:200],
            }
            print(json.dumps(log_entry, ensure_ascii=False))
            from app.services.trace_store import save_trace
            save_trace(log_entry)   # 异常路径没有 response，直接同步写
            raise                   # 继续抛给 FastAPI 转 500

        # 3. 耗时 + 慢请求标记
        total_time = time.time() - request.state.start_time
        log_entry = {
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "total_time": round(total_time, 3),
            "user_id": getattr(request.state, "user_id", None),
        }
        if total_time > SLOW_THRESHOLD:
            log_entry["slow"] = True  # 超时标签只打在控制台，不入库
        # 业务层挂上来的 agent/sentiment/intent，一起入账
        log_entry.update(getattr(request.state, "trace_info", {}))
        print(json.dumps(log_entry, ensure_ascii=False))

        # 4. 响应头回传 trace_id —— 前端报错时能提供这个 ID 来查
        response.headers["X-Trace-ID"] = trace_id

        # 5. 异步写 MySQL（不阻塞响应）
        from app.services.trace_store import save_trace
        response.background = BackgroundTask(save_trace, log_entry)

        return response
