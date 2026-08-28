"""对话系统核心逻辑单元测试（不依赖数据库）。

覆盖：意图识别、槽位提取、中文日期解析、对话状态流转、知识检索、
闲聊 / 澄清路由、任务型对话槽位收集（以桩 Action 替代真实 DB 调用）。
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.dialogue.actions.base import ActionResult, registry
from app.dialogue.engine import DialogueEngine
from app.dialogue.extractors import (
    extract_date,
    extract_order_no,
    extract_refund_type,
    extract_ticket_type,
)
from app.dialogue.intent import (
    INTENT_AMBIGUOUS,
    INTENT_CHITCHAT,
    INTENT_ORDER_STATUS,
    INTENT_POLICY,
    INTENT_PRODUCT_CONSULT,
    INTENT_REFUND,
    INTENT_TICKET,
    INTENT_TRIP_INFO,
    IntentRecognizer,
)
from app.dialogue.knowledge import retrieve
from app.dialogue.state import DialogueState
from app.utils import local_now


@pytest.fixture(scope="module")
def recognizer() -> IntentRecognizer:
    return IntentRecognizer()


@pytest.fixture()
def state() -> DialogueState:
    return DialogueState(session_id="test-session")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("你好", "greet"),
        ("谢谢", "thanks"),
        ("我要退款", INTENT_REFUND),
        ("我要投诉", INTENT_TICKET),
        ("帮我查下订单 ORD0000000001", INTENT_ORDER_STATUS),
        ("ORD0000000001", INTENT_ORDER_STATUS),
        ("我的订单 ORD0000000001 具体哪天入住", INTENT_TRIP_INFO),
        ("下周一我有啥出行安排", INTENT_TRIP_INFO),
        ("火车票退票手续费怎么收", INTENT_POLICY),
        ("酒店可以免费取消吗", INTENT_POLICY),
        ("三亚有哪些五星级度假酒店", INTENT_PRODUCT_CONSULT),
        ("G527 这趟高铁什么时候出发", INTENT_PRODUCT_CONSULT),
        ("今天天气怎么样", INTENT_CHITCHAT),
    ],
)
def test_intent_recognition(recognizer, text, expected):
    assert recognizer.recognize(text).intent == expected


def test_product_type_detection(recognizer):
    assert recognizer.recognize("三亚有哪些五星级度假酒店").product_type == "hotel"
    assert recognizer.recognize("G527 这趟高铁什么时候出发").product_type == "train"
    assert recognizer.recognize("从北京到上海的机票").product_type == "flight"


def test_ambiguous_intent(recognizer):
    result = recognizer.recognize("退款还是改签")
    assert result.intent == INTENT_AMBIGUOUS
    assert len(result.candidates) == 2


def test_extract_order_no():
    assert extract_order_no("订单 ORD0000000001 帮我查下") == "ORD0000000001"
    assert extract_order_no("ord20240501010") == "ORD20240501010"
    assert extract_order_no("没有订单号") is None


def test_extract_relative_date():
    today = local_now().date()
    next_monday = today + timedelta(days=7 - today.weekday())
    assert extract_date("下周一我有啥出行安排") == next_monday.isoformat()
    assert extract_date("明天出发") == (today + timedelta(days=1)).isoformat()
    assert extract_date("2026-05-01 出发") == "2026-05-01"


def test_extract_refund_and_ticket_type():
    assert extract_refund_type("我要全额退款") == "full"
    assert extract_refund_type("退一部分") == "partial"
    assert extract_ticket_type("我要投诉") == "complaint"
    assert extract_ticket_type("售后问题") == "after_sale"


def test_state_start_resume_cancel():
    s = DialogueState(session_id="s")
    s.start_task("refund")
    assert s.current_task == "refund"
    s.set_slot("order_no", "ORD0000000001")
    # 切换任务会暂存当前任务
    s.start_task("ticket")
    assert s.current_task == "ticket"
    assert s.pending_task is not None and s.pending_task["task"] == "refund"
    # 恢复
    assert s.resume_pending_task() is True
    assert s.current_task == "refund"
    assert s.slots.get("order_no") == "ORD0000000001"
    # 取消
    s.cancel_task()
    assert s.current_task is None


def test_knowledge_retrieve():
    result = retrieve("火车票退票手续费怎么收")
    assert result.found is True
    assert "退票" in result.answer


def test_chitchat_and_clarify_routing(state):
    engine = DialogueEngine()
    reply, _ = engine.process(state, "你好")
    assert "旅游" in reply.reply or "客服" in reply.reply
    reply, _ = engine.process(state, "退款还是改签")
    assert "想" in reply.reply  # 澄清话术


def test_refund_flow_with_stubbed_action(state, monkeypatch):
    calls: dict[str, object] = {}

    def fake_apply_refund(**ctx):
        calls["ctx"] = ctx
        return ActionResult(ok=True, action="apply_refund", text="退款申请已提交", data={})

    monkeypatch.setitem(registry._actions, "apply_refund", fake_apply_refund)
    engine = DialogueEngine()

    reply, _ = engine.process(state, "我要退款")
    assert state.current_task == "refund"
    assert "订单号" in reply.reply

    reply, _ = engine.process(state, "ORD0000000001")
    assert state.slots["order_no"] == "ORD0000000001"
    assert "原因" in reply.reply

    reply, _ = engine.process(state, "行程变更，全额退款")
    assert reply.reply == "退款申请已提交"
    assert state.current_task is None
    assert calls["ctx"]["order_no"] == "ORD0000000001"
    assert calls["ctx"]["refund_type"] == "full"


def test_ticket_flow_with_stubbed_action(state, monkeypatch):
    def fake_submit_ticket(**ctx):
        return ActionResult(ok=True, action="submit_ticket", text="工单已提交", data={})

    monkeypatch.setitem(registry._actions, "submit_ticket", fake_submit_ticket)
    engine = DialogueEngine()

    engine.process(state, "酒店房间和预订时描述的不一样，我要投诉")
    assert state.current_task == "ticket"
    assert state.slots.get("ticket_type") == "complaint"

    engine.process(state, "ORD0000000001")
    assert state.slots.get("order_no") == "ORD0000000001"

    reply, _ = engine.process(state, "房间有异味，和页面描述不符")
    assert reply.reply == "工单已提交"
    assert state.current_task is None


def test_task_switch(state):
    engine = DialogueEngine()
    engine.process(state, "我要退款")
    assert state.current_task == "refund"
    # 无订单号的新任务触发切换
    engine.process(state, "先帮我查下订单")
    assert state.current_task == "order_status"
    assert state.pending_task is not None
    assert state.pending_task["task"] == "refund"


def test_task_cancel(state):
    engine = DialogueEngine()
    engine.process(state, "我要退款")
    assert state.current_task == "refund"
    reply, _ = engine.process(state, "算了，取消吧")
    assert state.current_task is None
    assert "取消" in reply.reply
