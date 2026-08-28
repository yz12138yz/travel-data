"""ChitchatHandler 实现。

对应电商小二「09 - ChitchatHandler 实现」。

处理问候、感谢与闲聊等非业务输入，给出自然友好的回复，
并适时引导用户回到业务场景。
"""

from __future__ import annotations

from typing import Any

from ..intent import INTENT_GREET, INTENT_THANKS, IntentResult
from .base import HandlerResult

_GREET_REPLIES = [
    "您好，我是旅游智能客服小旅，很高兴为您服务！您想咨询酒店、景区、机票火车票，还是查询订单、申请退款呢？",
    "您好呀！请问有什么可以帮您？例如「三亚有哪些酒店」「帮我查下订单」「我要退款」。",
]

_THANKS_REPLIES = [
    "不客气，祝您旅途愉快！还有其他需要帮忙的吗？",
    "能帮到您是我的荣幸，随时欢迎再来咨询～",
]

_CHITCHAT_REPLIES = [
    "这个问题我不太确定，不过关于旅游出行的问题我都很乐意解答～您可以问我酒店、景区、交通票务、订单或退款相关的问题。",
    "我们聊聊出行相关的话题吧？比如「三亚有哪些五星酒店」「G1 高铁什么时候出发」或「我要退款」。",
]


class ChitchatHandler:
    """闲聊处理器。"""

    def handle(self, text: str, intent_result: IntentResult | None = None) -> HandlerResult:
        intent = intent_result.intent if intent_result else ""
        # 使用文本长度做简单的轮换，避免每次回复都一样
        idx = len((text or "").strip()) % 2
        if intent == INTENT_GREET:
            return HandlerResult(reply=_GREET_REPLIES[idx], intent="greet")
        if intent == INTENT_THANKS:
            return HandlerResult(reply=_THANKS_REPLIES[idx], intent="thanks")
        return HandlerResult(reply=_CHITCHAT_REPLIES[idx], intent="chitchat")
