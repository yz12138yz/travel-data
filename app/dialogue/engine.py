"""DialogueEngine 实现。

对应电商小二「06 - DialogueEngine 设计」「12 - DialogueEngine 实现」。

对话引擎是编排中枢，负责一次对话的完整链路：

    接收消息 → 对象槽位提取 → 意图识别 → Planning 规划轨道
             → 处理器执行（任务 / 知识 / 闲聊 / 澄清）→ 生成回复 → 更新状态

并在此过程中记录执行轨迹（TraceStep），满足可观测性要求。
"""

from __future__ import annotations

from typing import Any

from .actions.products import consult_product
from .handlers.base import HandlerResult
from .handlers.chitchat import ChitchatHandler
from .handlers.knowledge import KnowledgeHandler
from .handlers.task import TASK_FLOWS, TaskHandler, collect_slots
from .intent import (
    INTENT_AMBIGUOUS,
    INTENT_CHITCHAT,
    INTENT_PRODUCT_CONSULT,
    IntentRecognizer,
    IntentResult,
)
from .planning import ROUTE_CHITCHAT, ROUTE_CLARIFY, ROUTE_KNOWLEDGE, ROUTE_PRODUCT, ROUTE_TASK, TASK_INTENTS, Planner
from .responder import ClarifyResponder
from .state import DialogueState, TraceStep

_CANCEL_KEYWORDS = ["取消", "算了", "不用了", "不退了", "先不", "取消任务", "不办了", "别退了"]


def _is_cancel(text: str) -> bool:
    return any(k in text for k in _CANCEL_KEYWORDS)


def _extract_object_slots(business_object: dict[str, Any] | None) -> dict[str, Any]:
    """从业务对象消息中提取槽位（订单对象 / 产品对象）。"""
    if not business_object:
        return {}
    mapping = {
        "order_no": "order_no", "orderNo": "order_no", "order_number": "order_no",
        "travel_date": "travel_date", "travelDate": "travel_date", "date": "travel_date",
        "phone": "phone",
    }
    slots: dict[str, Any] = {}
    for key, value in business_object.items():
        if key in mapping and value not in (None, ""):
            slots[mapping[key]] = str(value)
    return slots


class DialogueEngine:
    """对话引擎。"""

    def __init__(self) -> None:
        self.recognizer = IntentRecognizer()
        self.planner = Planner()
        self.task_handler = TaskHandler()
        self.knowledge_handler = KnowledgeHandler()
        self.chitchat_handler = ChitchatHandler()
        self.clarify_responder = ClarifyResponder()

    def process(
        self,
        state: DialogueState,
        text: str,
        message_type: str = "text",
        business_object: dict[str, Any] | None = None,
    ) -> tuple[HandlerResult, list[TraceStep]]:
        trace: list[TraceStep] = []
        text = (text or "").strip()
        trace.append(TraceStep("receive", {"text": text, "message_type": message_type}))

        # 1. 业务对象消息：自动提取对象信息，尝试匹配当前任务所需槽位
        if message_type in ("order", "product") and business_object:
            obj_slots = _extract_object_slots(business_object)
            state.slots.update(obj_slots)
            trace.append(TraceStep("extract_object", dict(obj_slots)))

        # 2. 意图识别（空文本按闲聊处理）
        intent_result = self.recognizer.recognize(text) if text else IntentResult(
            intent=INTENT_CHITCHAT, confidence=0.3
        )
        trace.append(TraceStep("recognize_intent", intent_result.to_dict()))

        # 3. 存在进行中的任务
        if state.current_task is not None:
            if _is_cancel(text):
                task = state.current_task
                state.cancel_task()
                trace.append(TraceStep("cancel_task", {"task": task}))
                return HandlerResult(
                    reply="好的，已为您取消当前任务。您还有其他需要帮忙的吗？",
                    intent="cancel",
                ), trace

            # 流程切换：用户发起新的任务，且当前输入未填充当前任务的结构化槽位时切换
            if intent_result.intent in TASK_INTENTS and intent_result.intent != state.current_task:
                flow = TASK_FLOWS[state.current_task]
                filled = collect_slots(flow, state, text, skip_free_text=True)
                if not filled:
                    old_task = state.current_task
                    state.start_task(intent_result.intent)
                    trace.append(TraceStep("switch_task", {"from": old_task, "to": intent_result.intent}))
                    result = self.task_handler.continue_(state, text, intent_result, initial=True)
                    return result, trace

            result = self.task_handler.continue_(state, text, intent_result)
            return result, trace

        # 4. 无进行中任务：按规划轨道路由
        plan = self.planner.decide(state, intent_result)
        trace.append(TraceStep("plan", {"route": plan.route, "task": plan.task_name}))

        if plan.route == ROUTE_TASK:
            state.start_task(plan.task_name)
            result = self.task_handler.continue_(state, text, intent_result, initial=True)
        elif plan.route == ROUTE_PRODUCT:
            action_result = consult_product(plan.product_type or "hotel", text)
            result = HandlerResult(reply=action_result.text, intent=INTENT_PRODUCT_CONSULT,
                                   data=action_result.data)
        elif plan.route == ROUTE_KNOWLEDGE:
            result = self.knowledge_handler.handle(text, intent_result)
        elif plan.route == ROUTE_CLARIFY:
            result = self.clarify_responder.respond(intent_result)
        else:  # ROUTE_CHITCHAT
            result = self.chitchat_handler.handle(text, intent_result)

        return result, trace
