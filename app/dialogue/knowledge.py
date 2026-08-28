"""知识库（FAQ / 政策）与检索。

对应电商小二「08 - KnowledgeHandler 实现」。

这里内置一份旅游行业的 FAQ / 政策条目。检索采用关键词加权匹配，
优先返回最匹配条目；命中率过低时回退到人工引导。未来可无缝替换为
向量检索 / RAG 实现，只需保持 ``retrieve`` 的返回结构不变。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 知识条目：question 为典型问法，keywords 用于匹配，answer 为客服回复
KNOWLEDGE_ITEMS: list[dict[str, Any]] = [
    {
        "id": "hotel_refund_policy",
        "category": "退改政策",
        "keywords": ["酒店", "退改", "取消", "退款", "退订", "提前"],
        "answer": (
            "酒店退改政策：入住日前 24 小时以上可免费取消；"
            "入住日前 24 小时内取消或未入住，将收取首晚房费作为违约金。具体以订单详情页展示的预订规则为准。"
        ),
    },
    {
        "id": "scenic_refund_policy",
        "category": "退改政策",
        "keywords": ["景区", "门票", "退改", "退款", "取消", "退票"],
        "answer": (
            "景区门票退改政策：游玩日前可免费退票；游玩当日及之后一般不支持退款。"
            "部分特惠票、夜场票退改规则可能不同，请以具体票种说明为准。"
        ),
    },
    {
        "id": "flight_refund_policy",
        "category": "退改政策",
        "keywords": ["机票", "航班", "退改签", "改签", "退票", "手续费", "舱位"],
        "answer": (
            "机票退改签政策：按舱位等级与出票折扣不同，退改手续费各异。"
            "经济舱特价票通常不支持退票、仅可改签；商务舱退改相对灵活。请提供订单号，我可为您查询具体可退金额。"
        ),
    },
    {
        "id": "train_refund_policy",
        "category": "退改政策",
        "keywords": ["火车票", "高铁", "动车", "退票", "改签", "手续费", "车票"],
        "answer": (
            "火车票退票规则：开车前 8 天以上退票免收手续费；开车前 48 小时以上按票价 5% 收取；"
            "开车前 24 小时以上按 10% 收取；开车前不足 24 小时按 20% 收取。改签后车票退票按新票办理。"
        ),
    },
    {
        "id": "bus_refund_policy",
        "category": "退改政策",
        "keywords": ["汽车票", "大巴", "班车", "退票", "改签", "手续费"],
        "answer": (
            "汽车票退改政策：发车前 2 小时以上可免费退票；发车前 2 小时以内或发车后不支持退票，请合理安排出行时间。"
        ),
    },
    {
        "id": "transfer_refund_policy",
        "category": "退改政策",
        "keywords": ["接送", "接机", "送机", "包车", "退改", "取消", "退款"],
        "answer": (
            "接送服务取消政策：用车前 4 小时以上可免费取消；用车前 4 小时以内取消将收取订单金额的 50% 作为违约金。"
        ),
    },
    {
        "id": "hotel_booking_rule",
        "category": "预订规则",
        "keywords": ["酒店", "预订", "入住时间", "退房时间", "几点入住", "押金"],
        "answer": (
            "酒店预订规则：常规入住时间为 14:00 后，退房时间为 12:00 前。部分酒店支持延迟退房，"
            "入住时可能需要支付押金，具体以酒店前台要求为准。"
        ),
    },
    {
        "id": "scenic_booking_rule",
        "category": "预订规则",
        "keywords": ["景区", "门票", "预订", "开放时间", "入园", "几点开门"],
        "answer": (
            "景区预订规则：建议提前一天购票预约，入园时凭身份证或订单二维码核销。"
            "各景区开放时间不同，通常为 08:30 - 17:00，具体请以景区详情页为准。"
        ),
    },
    {
        "id": "id_verification",
        "category": "出行须知",
        "keywords": ["身份证", "实名", "证件", "核验", "出行人"],
        "answer": (
            "出行须知：乘坐飞机、火车及入住酒店均需实名登记，请携带本人有效身份证件；"
            "购买机票、火车票前请确认出行人姓名与证件号填写无误。"
        ),
    },
    {
        "id": "luggage_rule",
        "category": "出行须知",
        "keywords": ["行李", "托运", "随身", "限重", "超重"],
        "answer": (
            "行李须知：国内航班经济舱免费托运一般为 20kg，随身携带行李 5kg；"
            "高铁随身行李一般限 20kg，无免费托运。超重需按规定付费。"
        ),
    },
    {
        "id": "payment_method",
        "category": "使用指南",
        "keywords": ["支付", "付款", "支付宝", "微信", "银联", "怎么付款"],
        "answer": (
            "平台支持支付宝、微信支付与银联在线支付。订单创建后请在 30 分钟内完成支付，超时订单将自动取消。"
        ),
    },
    {
        "id": "contact_human",
        "category": "使用指南",
        "keywords": ["人工", "客服电话", "联系客服", "转人工", "投诉"],
        "answer": (
            "如需人工服务，您可以直接对我说「我要提交工单」，我将引导您创建工单；"
            "或拨打客服热线 400-888-0000（服务时间 09:00 - 21:00）。"
        ),
    },
    {
        "id": "coupon_usage",
        "category": "使用指南",
        "keywords": ["优惠券", "优惠", "券", "满减", "折扣"],
        "answer": (
            "优惠券使用说明：下单结算时系统会自动匹配可用优惠券，满减券需满足门槛金额，"
            "每张券限用一次，具体以券面规则为准。"
        ),
    },
    {
        "id": "refund_flow_guide",
        "category": "使用指南",
        "keywords": ["怎么退款", "退款流程", "如何退款", "退款多久", "到账"],
        "answer": (
            "退款流程：您可对我说「我要退款」，提供订单号并选择退款类型，提交后一般 1-3 个工作日原路退回。"
        ),
    },
]

FALLBACK_ANSWER = (
    "抱歉，我没有完全理解您的问题。您可以换个方式描述，或对我说「我要退款」「查订单」"
    "「提交工单」等，也可以说「转人工」获取人工协助。"
)


@dataclass
class KnowledgeResult:
    """知识检索结果。"""

    found: bool
    answer: str
    category: str | None = None
    matched_keywords: list[str] = field(default_factory=list)


def retrieve(query: str) -> KnowledgeResult:
    """基于关键词加权匹配，返回最相关的知识条目。"""
    best: dict[str, Any] | None = None
    best_score = 0
    best_keywords: list[str] = []
    for item in KNOWLEDGE_ITEMS:
        score = 0
        matched: list[str] = []
        for kw in item["keywords"]:
            if kw in query:
                score += 1
                matched.append(kw)
        if score > best_score:
            best_score = score
            best = item
            best_keywords = matched
    if best is None or best_score == 0:
        return KnowledgeResult(found=False, answer=FALLBACK_ANSWER)
    return KnowledgeResult(
        found=True,
        answer=best["answer"],
        category=best["category"],
        matched_keywords=best_keywords,
    )
