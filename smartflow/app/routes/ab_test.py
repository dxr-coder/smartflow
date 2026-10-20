"""
A/B 测试路由

数据流：
  GET /ab-test/stats   → 管理页：两组 CSAT 对比（admin）
  GET /ab-test/variant → 当前用户在哪个组（登录即可，chat 空状态 chip 用）
"""
from fastapi import APIRouter, Depends
from app.deps import get_current_user, require_role
from app.services.ab_test import get_experiment_stats, get_my_variant

router = APIRouter(prefix="/ab-test", tags=["A/B测试"])


@router.get("/stats")
def stats_route(user=Depends(require_role('admin'))):
    """管理员看实验对比（CSAT 口径）"""
    return get_experiment_stats()


@router.get("/variant")
def variant_route(user=Depends(get_current_user)):
    """当前用户看自己被分到哪个组"""
    return get_my_variant(user["user_id"])
