"""对话接口的请求 / 响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MessageType = Literal["text", "order", "product"]


class SessionCreateRequest(BaseModel):
    """创建会话请求体。"""

    userId: int | None = Field(default=None, description="旅客 ID（users.id），可为空。")


class MessageSendRequest(BaseModel):
    """发送消息请求体。"""

    content: str = Field(description="文本消息内容；消息类型为业务对象时可为空。")
    messageType: MessageType = Field(
        default="text", description="消息类型：text=文本，order=订单对象，product=产品对象。"
    )
    businessObject: dict[str, Any] | None = Field(
        default=None, description="业务对象（当 messageType 为 order/product 时携带）。"
    )


class StateView(BaseModel):
    """会话状态快照（对前端暴露）。"""

    sessionId: str
    userId: int | None = None
    currentTask: str | None = None
    taskStep: str | None = None
    slots: dict[str, Any] = Field(default_factory=dict)
    hasPendingTask: bool = False


class ReplyMessage(BaseModel):
    """助手回复消息。"""

    role: Literal["assistant"] = "assistant"
    content: str
    intent: str | None = None


class TraceItem(BaseModel):
    """对话处理轨迹节点。"""

    step: str
    detail: dict[str, Any] = Field(default_factory=dict)


class SendMessageResponse(BaseModel):
    """发送消息（非流式）响应体。"""

    sessionId: str
    reply: ReplyMessage
    state: StateView
    trace: list[TraceItem] = Field(default_factory=list)


class SessionStateResponse(BaseModel):
    """获取会话状态响应体。"""

    sessionId: str
    state: StateView


class MessageItem(BaseModel):
    """历史消息。"""

    role: Literal["user", "assistant"]
    content: str
    intent: str | None = None
    createdAt: str | None = None


class SessionHistoryResponse(BaseModel):
    """会话历史响应体。"""

    sessionId: str
    messages: list[MessageItem]
