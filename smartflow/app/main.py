"""
SmartFlow — AI 智能客服系统

功能：FastAPI 应用入口，注册所有路由，启动应用。
"""

from dotenv import load_dotenv

# 先加载 .env 里的环境变量（API key、数据库密码），后面所有 import 都能读到
load_dotenv()

from fastapi import FastAPI
from app.routes.auth import router as auth_router
from app.routes.ticket import router as ticket_router
from app.routes.transfer import router as transfer_router
from app.routes.pdf import router as pdf_router
from app.routes.chat import router as chat_router
from app.routes.conversation import router as conversation_router
from app.routes.user import router as user_router
from app.routes.document import router as document_router
from app.routes.stats import router as stats_router
from app.middleware import TraceMiddleware
from contextlib import asynccontextmanager
from app.services.sla_engine import start_sla_scheduler, stop_sla_scheduler
from app.routes.feedback import router as feedback_router
from app.routes.audit import router as audit_router
from app.routes.ab_test import router as ab_router
from app.routes.asset import router as asset_router
from app.routes.csat import router as csat_router
from app.routes.eval import router as eval_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 服务器启动时：拉起 SLA 后台扫描线程
    start_sla_scheduler()
    yield  # 这里是服务器运行期间，yield 之后 = 关服时刻
    # 服务器关闭时：停掉后台线程，防止脏退出
    stop_sla_scheduler()


app = FastAPI(
    title="SmartFlow",
    description="AI 智能客服系统",
    version="2.0",
    lifespan=lifespan,
)

# 中间件：所有路由最外层包一圈，负责 trace_id / 限流 / 日志
app.add_middleware(TraceMiddleware)
# 注册路由：每个 router 自带 prefix，最终路径 = prefix + 接口路径
app.include_router(auth_router)
app.include_router(ticket_router)
app.include_router(transfer_router)
app.include_router(pdf_router)
app.include_router(chat_router)
app.include_router(conversation_router)
app.include_router(user_router)
app.include_router(document_router)
app.include_router(stats_router)
app.include_router(feedback_router)
app.include_router(audit_router)
app.include_router(ab_router)
app.include_router(asset_router)
app.include_router(csat_router)
app.include_router(eval_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
