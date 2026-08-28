"""Action 基础设施：结果模型与注册表。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ActionResult:
    """Action 执行结果。

    Attributes:
        ok: 是否执行成功。
        text: 面向用户的自然语言回复。
        data: 结构化数据（用于 trace 与前端展示）。
        action: 动作名，用于审计与轨迹。
    """

    ok: bool
    text: str
    data: dict[str, Any] = field(default_factory=dict)
    action: str = ""


ActionFn = Callable[..., ActionResult]


class ActionRegistry:
    """Action 注册表。"""

    def __init__(self) -> None:
        self._actions: dict[str, ActionFn] = {}

    def register(self, name: str) -> Callable[[ActionFn], ActionFn]:
        def decorator(fn: ActionFn) -> ActionFn:
            self._actions[name] = fn
            return fn

        return decorator

    def get(self, name: str) -> ActionFn | None:
        return self._actions.get(name)

    def names(self) -> list[str]:
        return list(self._actions.keys())


registry = ActionRegistry()


def run_action(name: str, **context: Any) -> ActionResult:
    """按名执行 Action；未注册时返回友好兜底。"""
    fn = registry.get(name)
    if fn is None:
        return ActionResult(
            ok=False,
            action=name,
            text="抱歉，该能力暂未开通，您可以尝试其他问题或转人工服务。",
        )
    try:
        return fn(**context)
    except Exception as exc:  # noqa: BLE001 —— 单次动作失败不影响整体服务
        return ActionResult(
            ok=False,
            action=name,
            text=f"查询时遇到了一点问题，请稍后重试或转人工处理。",
            data={"error": str(exc)},
        )
