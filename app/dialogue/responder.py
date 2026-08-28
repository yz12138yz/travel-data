"""ClarifyResponder 实现。

对应电商小二「11 - ClarifyResponder 实现」。

当意图识别结果存在歧义（同时命中多个意图）或无法确定时，主动向用户
澄清，而不是直接给出错误回复。
"""

from __future__ import annotations

from .intent import IntentResult
from .handlers.base import HandlerResult

INTENT_LABELS = {
    "refund": "申请退款",
    "ticket": "提交工单",
    "trip_info": "查询出行信息",
    "order_status": "查询订单",
    "policy": "咨询退改政策",
    "product_consult": "咨询产品",
}

_GENERIC_CLARIFY = (
    "我没有完全理解您的意思，能否说得更具体一些？例如："
    "「查订单」「我要退款」「我要投诉」「三亚有哪些酒店」。"
)


class ClarifyResponder:
    """意图澄清响应器。"""

    def respond(self, intent_result: IntentResult) -> HandlerResult:
        candidates = intent_result.candidates
        if candidates:
            labels = [INTENT_LABELS.get(c, c) for c in candidates]
            reply = f"您的问题我有点不确定，请问您是想{'，还是想'.join(labels)}？"
            return HandlerResult(reply=reply, intent="clarify",
                                 data={"candidates": candidates})
        return HandlerResult(reply=_GENERIC_CLARIFY, intent="clarify")
