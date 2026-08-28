"""TaskHandler 实现。

对应电商小二「07 - TaskHandler 实现」。

任务型对话以「配置化流程」驱动：每个任务定义一组有序槽位，
TaskHandler 负责槽位收集、缺失追问、执行 Action、以及完成后的状态清理。
新增任务只需在 ``TASK_FLOWS`` 中增加配置，无需修改核心代码（可扩展性）。
"""

from __future__ import annotations

from typing import Any

from ..actions.base import run_action
from ..extractors import EXTRACTORS
from ..intent import IntentResult
from .base import HandlerResult

# 任务流程配置：任务名 -> 流程定义
TASK_FLOWS: dict[str, dict[str, Any]] = {
    "order_status": {
        "label": "订单状态查询",
        "action": "query_order_status",
        "slots": [
            {"name": "order_no", "extractor": "order_no",
             "prompt": "请提供要查询的订单号（例如 ORD0000000001）"},
        ],
    },
    "trip_info": {
        "label": "出行信息查询",
        "action": "query_trip_info",
        "slots": [
            {"name": "target", "extractor": "trip_target",
             "prompt": "请提供订单号或出行日期，我来帮您查询出行信息"},
        ],
    },
    "refund": {
        "label": "退款申请",
        "action": "apply_refund",
        "slots": [
            {"name": "order_no", "extractor": "order_no",
             "prompt": "请提供需要退款的订单号（例如 ORD0000000001）"},
            {"name": "refund_reason", "extractor": "free_text",
             "prompt": "请说明退款原因（例如：行程变更、重复预订、商品不符等）"},
            {"name": "refund_type", "extractor": "refund_type",
             "prompt": "请选择退款类型：全额退款 / 部分退款"},
        ],
    },
    "ticket": {
        "label": "工单提交",
        "action": "submit_ticket",
        "slots": [
            {"name": "ticket_type", "extractor": "ticket_type",
             "prompt": "请问您需要提交哪类工单？（售后 / 投诉 / 退款）"},
            {"name": "order_no", "extractor": "order_no_optional",
             "prompt": "请提供关联的订单号（若无关联订单，请回复“无”）"},
            {"name": "problem_desc", "extractor": "free_text",
             "prompt": "请简单描述您遇到的问题"},
        ],
    },
}


def collect_slots(flow: dict[str, Any], state: Any, text: str, skip_free_text: bool = False) -> list[str]:
    """从用户输入中提取可填充的槽位，返回本轮新填充的槽位名列表。

    ``skip_free_text`` 用于任务刚开启的首条触发消息：此时文本主体是意图表达
    （如「我要退款」），不应被自由文本槽位误收为退款原因 / 问题描述。
    """
    filled: list[str] = []
    slots = flow["slots"]
    for i, slot in enumerate(slots):
        if slot["name"] in state.slots:
            continue
        if slot["extractor"] == "free_text":
            # 自由文本槽位只在它是「当前缺失槽位」时收集，避免把用户对
            # 前面槽位的回答（如回复「无」表示不关联订单）误当成描述 / 原因。
            if skip_free_text:
                continue
            if any(s["name"] not in state.slots for s in slots[:i]):
                continue
        extractor = EXTRACTORS[slot["extractor"]]
        value = extractor(text, state)
        if value is not None:
            state.slots[slot["name"]] = value
            filled.append(slot["name"])
    return filled


def next_missing_slot(flow: dict[str, Any], state: Any) -> dict[str, Any] | None:
    for slot in flow["slots"]:
        if slot["name"] not in state.slots:
            return slot
    return None


class TaskHandler:
    """任务型对话处理器。

    无论任务刚开启还是进行中，均通过 ``continue_`` 统一处理：
    先从本轮输入中收集槽位，若有缺失则追问，否则执行 Action。
    """

    def continue_(self, state: Any, text: str, intent_result: IntentResult,
                  initial: bool = False) -> HandlerResult:
        """收集当前任务槽位，收集完成后执行 Action。

        ``initial=True`` 表示该消息是任务开启的首条触发消息（跳过自由文本槽位）。
        """
        flow = TASK_FLOWS[state.current_task]
        collect_slots(flow, state, text, skip_free_text=initial)

        # 将识别阶段得到的槽位并入（如订单号 / 日期）
        for key, value in intent_result.slots.items():
            if value and key not in state.slots:
                state.slots[key] = value

        missing = next_missing_slot(flow, state)
        if missing is not None:
            state.task_step = missing["name"]
            return HandlerResult(
                reply=missing["prompt"],
                intent=state.current_task,
                data={"task": state.current_task, "task_step": missing["name"]},
            )

        # 槽位齐全，执行 Action
        result = run_action(flow["action"], user_id=state.user_id, session_id=state.session_id,
                            **state.slots)
        state.cancel_task()
        return HandlerResult(reply=result.text, intent=flow["action"],
                            data={**result.data, "task": flow["label"]})
