"""Planning 模块。

对应电商小二「10 - Planning 模块实现」。

将识别出的意图规划为一条执行「轨道」（route），并规划任务型对话的
槽位收集路径。核心逻辑集中在 ``Planner.decide``，便于后续替换为
LLM 规划实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .intent import (
    INTENT_AMBIGUOUS,
    INTENT_CHITCHAT,
    INTENT_GREET,
    INTENT_ORDER_STATUS,
    INTENT_POLICY,
    INTENT_PRODUCT_CONSULT,
    INTENT_REFUND,
    INTENT_THANKS,
    INTENT_TICKET,
    INTENT_TRIP_INFO,
    IntentResult,
)
from .state import DialogueState

# 轨道常量
ROUTE_TASK = "task"
ROUTE_PRODUCT = "product"
ROUTE_KNOWLEDGE = "knowledge"
ROUTE_CHITCHAT = "chitchat"
ROUTE_CLARIFY = "clarify"

# 任务型意图
TASK_INTENTS = {INTENT_REFUND, INTENT_TICKET, INTENT_ORDER_STATUS, INTENT_TRIP_INFO}

_INTENT_TO_ROUTE = {
    INTENT_REFUND: ROUTE_TASK,
    INTENT_TICKET: ROUTE_TASK,
    INTENT_ORDER_STATUS: ROUTE_TASK,
    INTENT_TRIP_INFO: ROUTE_TASK,
    INTENT_PRODUCT_CONSULT: ROUTE_PRODUCT,
    INTENT_POLICY: ROUTE_KNOWLEDGE,
    INTENT_GREET: ROUTE_CHITCHAT,
    INTENT_THANKS: ROUTE_CHITCHAT,
    INTENT_CHITCHAT: ROUTE_CHITCHAT,
    INTENT_AMBIGUOUS: ROUTE_CLARIFY,
}


@dataclass
class Plan:
    """规划结果。"""

    route: str
    task_name: str | None = None
    product_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class Planner:
    """意图规划器。"""

    def decide(self, state: DialogueState, intent_result: IntentResult) -> Plan:
        # 存在进行中的任务时，优先继续当前任务轨道（除非引擎判定为流程切换）
        if state.current_task is not None:
            return Plan(route=ROUTE_TASK, task_name=state.current_task,
                        detail={"mode": "continue"})

        route = _INTENT_TO_ROUTE.get(intent_result.intent, ROUTE_CHITCHAT)
        if route == ROUTE_TASK:
            return Plan(route=route, task_name=intent_result.intent)
        if route == ROUTE_PRODUCT:
            return Plan(route=route, product_type=intent_result.product_type)
        return Plan(route=route)
