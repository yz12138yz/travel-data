"""意图定义与规则识别器。

对应电商小二「06 - DialogueEngine 设计」中的意图识别部分。

说明：本实现使用「关键词加权 + 优先级」的规则识别，无需外部大模型，
便于离线演示与自动化测试。识别器以类接口对外暴露（``recognize``），
未来可替换为 LLM 意图识别实现而不改动编排逻辑（可插拔）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .extractors import extract_date, extract_order_no, extract_phone

# ---- 意图常量 -------------------------------------------------------------
INTENT_REFUND = "refund"
INTENT_TICKET = "ticket"
INTENT_TRIP_INFO = "trip_info"
INTENT_ORDER_STATUS = "order_status"
INTENT_POLICY = "policy"
INTENT_PRODUCT_CONSULT = "product_consult"
INTENT_GREET = "greet"
INTENT_THANKS = "thanks"
INTENT_CHITCHAT = "chitchat"
INTENT_AMBIGUOUS = "ambiguous"

# ---- 产品类型常量 ----------------------------------------------------------
PRODUCT_HOTEL = "hotel"
PRODUCT_SCENIC = "scenic"
PRODUCT_FLIGHT = "flight"
PRODUCT_TRAIN = "train"
PRODUCT_BUS = "bus"
PRODUCT_TRANSFER = "transfer"

# 产品类型 -> 关键词 -> 权重
PRODUCT_KEYWORDS: dict[str, dict[str, int]] = {
    PRODUCT_HOTEL: {
        "酒店": 2, "宾馆": 2, "住宿": 2, "房型": 2, "房间": 1,
        "度假酒店": 3, "民宿": 2, "五星": 2, "豪华": 1, "入住": 1,
    },
    PRODUCT_SCENIC: {
        "景区": 2, "景点": 2, "门票": 2, "游玩": 2, "公园": 1,
        "博物馆": 2, "游乐": 1, "5A": 2, "4A": 2, "3A": 2, "动物园": 2,
    },
    PRODUCT_FLIGHT: {
        "机票": 3, "飞机": 2, "航班": 3, "航空": 2, "经济舱": 2,
        "商务舱": 2, "起飞": 1, "航线": 2, "乘机": 2,
    },
    PRODUCT_TRAIN: {
        "火车票": 3, "高铁": 3, "动车": 2, "车次": 3, "火车": 2,
        "二等座": 2, "一等座": 2, "商务座": 2, "列车": 2,
    },
    PRODUCT_BUS: {
        "汽车票": 3, "大巴": 2, "班车": 2, "长途汽车": 2, "客车": 2, "汽车": 1,
    },
    PRODUCT_TRANSFER: {
        "接送": 3, "接机": 3, "送机": 3, "包车": 2, "专车": 2, "用车": 2, "接送机": 3,
    },
}

# 非产品意图 -> 关键词 -> 权重
INTENT_KEYWORDS: dict[str, dict[str, int]] = {
    INTENT_REFUND: {
        "退款": 4, "退票": 4, "退货": 3, "申请退款": 5, "我要退": 5, "退订": 3,
    },
    INTENT_TICKET: {
        "投诉": 6, "工单": 5, "转人工": 5, "人工客服": 5, "售后": 3,
        "反馈": 2, "不满意": 2, "差评": 2, "投诉处理": 5,
    },
    INTENT_TRIP_INFO: {
        "出行信息": 6, "行程": 5, "出行安排": 6, "哪天入住": 6, "什么时候入住": 6,
        "入住日期": 6, "退房日期": 4, "出行": 1,
    },
    INTENT_ORDER_STATUS: {
        "订单状态": 5, "查订单": 5, "订单查询": 5, "我的订单": 4, "订单": 2, "订单号": 5,
    },
    INTENT_POLICY: {
        "退改": 5, "退改签": 5, "取消政策": 5, "政策": 5, "规则": 3,
        "手续费": 5, "须知": 3, "规定": 3, "预订规则": 5, "能退吗": 3, "可以退吗": 3,
        "退票费": 5, "改签": 3, "免费取消": 5, "可以取消吗": 3, "能取消吗": 3,
    },
    INTENT_GREET: {
        "你好": 3, "您好": 3, "在吗": 2, "hi": 2, "hello": 2,
        "早上好": 3, "下午好": 3, "晚上好": 3, "哈喽": 2, "嗨": 2,
    },
    INTENT_THANKS: {
        "谢谢": 3, "感谢": 3, "多谢": 3, "谢谢您": 3, "辛苦了": 2,
    },
}

# 得分相同时的优先级（越靠前越优先）
PRIORITY: list[str] = [
    INTENT_TRIP_INFO,
    INTENT_ORDER_STATUS,
    INTENT_POLICY,
    INTENT_REFUND,
    INTENT_TICKET,
    INTENT_PRODUCT_CONSULT,
    INTENT_GREET,
    INTENT_THANKS,
    INTENT_CHITCHAT,
]

# 选择 / 并列词：出现时若命中多个意图，视为歧义交由澄清
_DISJUNCTION_WORDS = ("还是", "或者", "或是", "要么")

@dataclass
class IntentResult:
    """意图识别结果。"""

    intent: str
    confidence: float
    matched: list[str] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    product_type: str | None = None
    candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "matched": self.matched,
            "slots": self.slots,
            "product_type": self.product_type,
            "candidates": self.candidates,
        }


def _score(text: str, keywords: dict[str, int]) -> tuple[int, list[str]]:
    """统计关键词命中，返回 (总得分, 命中关键词列表)。

    按关键词长度降序匹配，避免「我的订单」与「订单」「火车票」与「火车」
    这类包含关系被重复计分。
    """
    total = 0
    matched: list[str] = []
    for word in sorted(keywords, key=len, reverse=True):
        if word in text and not any(word in m for m in matched):
            total += keywords[word]
            matched.append(word)
    return total, matched


class IntentRecognizer:
    """规则意图识别器（可替换为 LLM 实现）。"""

    def recognize(self, text: str) -> IntentResult:
        text = (text or "").strip()
        scores: dict[str, int] = {}
        matched: dict[str, list[str]] = {}

        for intent, keywords in INTENT_KEYWORDS.items():
            s, m = _score(text, keywords)
            if s:
                scores[intent] = s
                matched[intent] = m

        # 产品咨询：按产品类型累加得分，取最高者作为 product_type
        product_score = 0
        product_type: str | None = None
        product_matched: list[str] = []
        for ptype, keywords in PRODUCT_KEYWORDS.items():
            s, m = _score(text, keywords)
            if s > product_score:
                product_score = s
                product_type = ptype
                product_matched = m
        if product_score:
            scores[INTENT_PRODUCT_CONSULT] = product_score
            matched[INTENT_PRODUCT_CONSULT] = product_matched

        slots = {
            "order_no": extract_order_no(text),
            "phone": extract_phone(text),
            "travel_date": extract_date(text),
        }

        # 无任何业务意图命中
        if not scores:
            if slots["order_no"]:
                return IntentResult(
                    intent=INTENT_ORDER_STATUS,
                    confidence=0.8,
                    matched=["订单号"],
                    slots=slots,
                )
            return IntentResult(
                intent=INTENT_CHITCHAT,
                confidence=0.3,
                matched=[],
                slots=slots,
            )

        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], PRIORITY.index(kv[0])))
        top_intent, top_score = ranked[0]

        candidates: list[str] = []
        # 歧义检测：出现「还是 / 或者」等选择词且命中多个意图时，交由澄清
        if any(w in text for w in _DISJUNCTION_WORDS) and len(ranked) >= 2:
            candidates = [ranked[0][0], ranked[1][0]]
            return IntentResult(
                intent=INTENT_AMBIGUOUS,
                confidence=0.5,
                matched=matched.get(top_intent, []),
                slots=slots,
                product_type=product_type,
                candidates=candidates,
            )

        confidence = min(0.95, 0.4 + 0.15 * top_score)
        return IntentResult(
            intent=top_intent,
            confidence=confidence,
            matched=matched.get(top_intent, []),
            slots=slots,
            product_type=product_type if top_intent == INTENT_PRODUCT_CONSULT else None,
            candidates=candidates,
        )
