"""对话接口（FastAPI）。

对应电商小二「13 - FastAPI 接口与应用生命周期」。

提供会话管理与非流式 / 流式（SSE）对话接口。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .schemas import (
    MessageSendRequest,
    SendMessageResponse,
    SessionCreateRequest,
    SessionHistoryResponse,
    SessionStateResponse,
)
from .service import DialogueService

router = APIRouter(prefix="/api/dialogue", tags=["dialogue"])

service = DialogueService()


@router.post("/sessions", response_model=None, summary="创建对话会话")
def create_session(body: SessionCreateRequest) -> dict:
    return service.create_session(body.userId)


@router.get("/sessions/{session_id}", response_model=SessionStateResponse, summary="获取会话状态")
def get_session_state(session_id: str) -> dict:
    result = service.get_state(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


@router.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse, summary="获取历史消息")
def get_history(session_id: str) -> dict:
    result = service.get_history(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse, summary="发送消息（非流式）")
def send_message(session_id: str, body: MessageSendRequest) -> dict:
    result = service.send_message(
        session_id, body.content, body.messageType, body.businessObject
    )
    if result is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return result


@router.post("/sessions/{session_id}/messages/stream", summary="发送消息（流式 SSE）")
def send_message_stream(session_id: str, body: MessageSendRequest) -> StreamingResponse:
    generator = service.stream_message(
        session_id, body.content, body.messageType, body.businessObject
    )
    if generator is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    def event_stream():
        for chunk in generator:
            if chunk == "[DONE]":
                yield "data: [DONE]\n\n"
                break
            yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
