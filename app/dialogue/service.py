"""DialogueService 实现。

对应电商小二「03 - DialogueService 实现」。

会话级入口，串联状态仓库与对话引擎，对外提供：
- 会话创建 / 会话状态查询 / 历史消息查询
- 消息发送（非流式与流式）
- 状态持久化与会话恢复
"""

from __future__ import annotations

from typing import Any, Iterator

from .engine import DialogueEngine
from .state import DialogueState, TraceStep
from .state_repository import DialogueStateRepository


def _state_view(state: DialogueState) -> dict[str, Any]:
    return {
        "sessionId": state.session_id,
        "userId": state.user_id,
        "currentTask": state.current_task,
        "taskStep": state.task_step,
        "slots": state.slots,
        "hasPendingTask": state.pending_task is not None,
    }


class DialogueService:
    """对话服务。"""

    def __init__(self) -> None:
        self.engine = DialogueEngine()
        self.repository = DialogueStateRepository()

    # ---- 会话管理 ----------------------------------------------------------
    def create_session(self, user_id: int | None = None) -> dict[str, Any]:
        session_id = self.repository.create_session(user_id)
        state = self.repository.load_state(session_id)
        return {"sessionId": session_id, "state": _state_view(state)}

    def get_state(self, session_id: str) -> dict[str, Any] | None:
        state = self.repository.load_state(session_id)
        if state is None:
            return None
        return {"sessionId": session_id, "state": _state_view(state)}

    def get_history(self, session_id: str) -> dict[str, Any] | None:
        if self.repository.load_state(session_id) is None:
            return None
        messages = [
            {
                "role": m["role"],
                "content": m["content"],
                "intent": m["intent"],
                "createdAt": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in self.repository.get_messages(session_id)
        ]
        return {"sessionId": session_id, "messages": messages}

    # ---- 消息处理 ----------------------------------------------------------
    def send_message(
        self,
        session_id: str,
        content: str,
        message_type: str = "text",
        business_object: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        state = self.repository.load_state(session_id)
        if state is None:
            return None
        return self._handle(state, content, message_type, business_object)

    def stream_message(
        self,
        session_id: str,
        content: str,
        message_type: str = "text",
        business_object: dict[str, Any] | None = None,
    ) -> Iterator[str] | None:
        """流式返回：逐字产出回复内容，末尾产出终止标记。

        会话不存在时返回 ``None``（由接口层转换为 404）；否则返回生成器。
        """
        state = self.repository.load_state(session_id)
        if state is None:
            return None

        def generate() -> Iterator[str]:
            result = self._handle(state, content, message_type, business_object)
            for ch in result["reply"]["content"]:
                yield ch
            yield "[DONE]"

        return generate()

    # ---- 内部：一次完整处理链路 -------------------------------------------
    def _handle(
        self,
        state: DialogueState,
        content: str,
        message_type: str,
        business_object: dict[str, Any] | None,
    ) -> dict[str, Any]:
        # 记录用户消息
        self.repository.append_message(state.session_id, "user", content or "")

        handler_result, trace = self.engine.process(
            state, content, message_type, business_object
        )

        # 记录助手消息（携带意图与轨迹）
        self.repository.append_message(
            state.session_id, "assistant", handler_result.reply,
            intent=handler_result.intent, trace=trace,
        )

        # 持久化最新状态
        self.repository.save_state(state)

        return {
            "sessionId": state.session_id,
            "reply": {
                "role": "assistant",
                "content": handler_result.reply,
                "intent": handler_result.intent,
            },
            "state": _state_view(state),
            "trace": [t.to_dict() for t in trace],
        }
