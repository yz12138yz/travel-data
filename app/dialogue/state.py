"""DialogueState 设计与定义。

对应电商小二「04 - DialogueState 设计与定义」。

对话状态是贯穿多轮对话的核心对象，承载：
- 会话标识与旅客身份
- 当前激活的任务流程及其进行到的步骤
- 已收集的槽位信息（订单号、退款原因、出行日期等）
- 上下文信息（最近一次意图、最近一次执行结果、执行轨迹）
- 暂存任务（用于流程切换后恢复）
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TraceStep:
    """一次对话处理过程中的单个节点轨迹，用于可观测性。"""

    step: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "detail": self.detail}


@dataclass
class DialogueState:
    """对话状态。

    Attributes:
        session_id: 会话 ID，全局唯一。
        user_id: 旅客 ID（对应 ``users.id``），可能为空。
        current_task: 当前激活的任务名（例如 ``refund`` / ``ticket`` / ``order_status`` / ``trip_info``），
            为 ``None`` 表示当前没有进行中的任务。
        task_step: 当前任务正在收集的槽位名（用于状态展示与调试）。
        slots: 已收集的槽位，键为槽位名，值为提取结果。
        context: 上下文信息，例如 ``last_intent``、``last_result``。
        pending_task: 暂存任务（流程切换时保存，切换回来自动恢复）。
        updated_at: 最近更新时间戳字符串。
    """

    session_id: str = ""
    user_id: int | None = None
    current_task: str | None = None
    task_step: str | None = None
    slots: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    pending_task: dict[str, Any] | None = None
    updated_at: str = ""

    # ---- 任务流程管控 ----------------------------------------------------
    def start_task(self, task_name: str, step: str | None = None) -> None:
        """开启一个新任务（新任务到来时暂存当前任务，实现流程切换）。"""
        if self.current_task is not None:
            self.pending_task = {
                "task": self.current_task,
                "task_step": self.task_step,
                "slots": dict(self.slots),
            }
        self.current_task = task_name
        self.task_step = step
        self.slots = {}

    def resume_pending_task(self) -> bool:
        """恢复之前暂存的任务，返回是否有可恢复的任务。"""
        if not self.pending_task:
            return False
        self.current_task = self.pending_task["task"]
        self.task_step = self.pending_task["task_step"]
        self.slots = dict(self.pending_task["slots"])
        self.pending_task = None
        return True

    def cancel_task(self) -> None:
        """取消当前任务并清理对应状态。"""
        self.current_task = None
        self.task_step = None
        self.slots = {}
        self.pending_task = None

    def set_slot(self, name: str, value: Any) -> None:
        self.slots[name] = value

    # ---- 序列化 ----------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogueState":
        known = {
            "session_id",
            "user_id",
            "current_task",
            "task_step",
            "slots",
            "context",
            "pending_task",
            "updated_at",
        }
        return cls(**{k: v for k, v in data.items() if k in known})
