"""
对话路由

功能：定义对话相关的 HTTP 接口。
数据流：
  create_conversation → 新对话 id
  get_conversations → 我的对话列表
  get_conversation_messages → 某个对话的全部消息
  update_conversation_tags → 打/改标签
"""
from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_current_user
from app.services.conversation import (
    create_conversation, get_conversations, get_conversation_messages,
    update_conversation_tags
)

router = APIRouter(prefix="/conversations", tags=["对话"])


@router.post('')
def create_conversation_route(title: str = '', user=Depends(get_current_user)):
    """新开一个对话"""
    conv_id = create_conversation(user['user_id'], title or '新对话')  # 归属人取自 token
    return {"id": conv_id, "title": title or '新对话'}


@router.get('')
def get_conversations_route(user=Depends(get_current_user)):
    """列出我的所有对话"""
    return get_conversations(user['user_id'])


@router.get('/{conversation_id}/messages')
def get_messages_route(conversation_id, user=Depends(get_current_user)):
    """拉某个对话的全部消息"""
    return get_conversation_messages(conversation_id, user['user_id'])  # 带上 user_id，防止看别人的对话

@router.put('/{conversation_id}/tags')
def update_tags_route(conversation_id: int, tags: str = '', user=Depends(get_current_user)):
    """给对话打标签（覆盖式更新）"""
    update_conversation_tags(conversation_id, user['user_id'], tags)
    return {"ok": True}
