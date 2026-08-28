"""槽位提取器与中文日期解析。

供意图识别器与任务处理器共用：从用户输入文本或业务对象中提取
订单号、出行日期、手机号、退款类型、工单类型、问题描述等槽位。
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Callable

from ..utils import local_now

# 订单号：ORD 前缀 + 数字（兼容 ORD0000000001 与 ORD20240501010 两种样式）
ORDER_NO_RE = re.compile(r"ORD\d+", re.IGNORECASE)
# 手机号：中国大陆 11 位
PHONE_RE = re.compile(r"1[3-9]\d{9}")
# 标准日期：2024-05-01 / 2024/05/01 / 2024年5月1日
ISO_DATE_RE = re.compile(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?")

_WEEKDAYS = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
# 纯否定回答，不算有效自由文本
_NO_ANSWERS = {"无", "没有", "没", "无订单", "没有订单", "不关联", "不用", "不需要", "暂无"}
_RELATIVE = {
    "大后天": 3,
    "后天": 2,
    "明天": 1,
    "今天": 0,
}


def _norm_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_date_expr(text: str) -> date | None:
    """从文本中解析出行日期，支持标准日期、中文日期与相对日期。

    相对日期示例：今天 / 明天 / 后天 / 大后天 / 下周一 / 下周日 / 本周三。
    """
    m = ISO_DATE_RE.search(text)
    if m:
        d = _norm_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            return d

    today = local_now().date()
    # 相对日期优先级：先精确短语（避免“明天”被“今天”误匹配）
    for word, delta in _RELATIVE.items():
        if word in text:
            return today + timedelta(days=delta)

    m = re.search(r"(下周|下星期)([一二三四五六日天])", text)
    if m:
        return today + timedelta(days=7 - today.weekday() + _WEEKDAYS[m.group(2)])

    m = re.search(r"(本周|这周|星期|周)([一二三四五六日天])", text)
    if m:
        target = _WEEKDAYS[m.group(2)]
        return today + timedelta(days=(target - today.weekday()) % 7)
    return None


def extract_order_no(text: str, *_args: Any) -> str | None:
    m = ORDER_NO_RE.search(text or "")
    return m.group(0).upper() if m else None


def extract_phone(text: str, *_args: Any) -> str | None:
    m = PHONE_RE.search(text or "")
    return m.group(0) if m else None


def extract_date(text: str, *_args: Any) -> str | None:
    d = parse_date_expr(text or "")
    return d.isoformat() if d else None


def _strip_tokens(text: str) -> str:
    """去掉已单独提取的订单号 / 手机号 / 日期，避免重复进入自由文本槽位。"""
    result = ORDER_NO_RE.sub("", text)
    result = PHONE_RE.sub("", result)
    result = ISO_DATE_RE.sub("", result)
    result = re.sub(r"(下周|下星期|本周|这周)[一二三四五六日天]", "", result)
    for word in _RELATIVE:
        result = result.replace(word, "")
    return result.strip(" ，。,.、：:；;?？!！\t\n")


def extract_free_text(text: str, *_args: Any) -> str | None:
    """自由文本槽位：返回去掉结构化 token 后的剩余文本。

    纯「无 / 没有」这类否定回答不算有效描述（例如工单关联订单时回复「无」），
    返回 ``None``，交由上一层继续追问。
    """
    cleaned = _strip_tokens(text or "")
    if cleaned in _NO_ANSWERS:
        return None
    return cleaned if cleaned else None


def extract_refund_type(text: str, *_args: Any) -> str | None:
    """退款类型：full=全额退款，partial=部分退款。"""
    if re.search(r"全额|全退|全部退款", text):
        return "full"
    if re.search(r"部分|部份|退部分", text):
        return "partial"
    return None


def extract_ticket_type(text: str, *_args: Any) -> str | None:
    """工单类型：after_sale=售后，complaint=投诉，refund=退款。"""
    if "投诉" in text or "不满" in text or "差评" in text:
        return "complaint"
    if "售后" in text:
        return "after_sale"
    if "退款" in text:
        return "refund"
    return None


def extract_order_no_optional(text: str, state: Any = None) -> str | None:
    """工单关联订单号：可回复“无/没有”表示不关联。"""
    if re.search(r"^(无|没有|没|不需要|不用|不关联|暂无)$", text.strip()):
        return ""
    return extract_order_no(text)


def extract_trip_target(text: str, *_args: Any) -> str | None:
    """出行信息查询目标：订单号优先，其次出行日期。"""
    return extract_order_no(text) or extract_date(text)


# 槽位名 -> 提取函数，供任务流程配置引用
SlotExtractor = Callable[[str, Any], Any]

EXTRACTORS: dict[str, SlotExtractor] = {
    "order_no": extract_order_no,
    "phone": extract_phone,
    "travel_date": extract_date,
    "free_text": extract_free_text,
    "refund_type": extract_refund_type,
    "ticket_type": extract_ticket_type,
    "order_no_optional": extract_order_no_optional,
    "trip_target": extract_trip_target,
}
