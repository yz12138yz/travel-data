"""订单查询 / 出行信息查询 Action。"""

from __future__ import annotations

import re
from typing import Any

from ...database import fetch_all, fetch_one
from ...utils import format_datetime
from .base import ActionResult, registry

ORDER_TYPE_DISPLAY = {
    "hotel_room": "酒店订单",
    "scenic_ticket": "景点门票订单",
    "flight_cabin": "机票订单",
    "train_seat": "火车票订单",
    "bus_seat": "汽车票订单",
    "transfer_service": "接送服务订单",
}
ORDER_STATUS_DISPLAY = {
    "pending_payment": "待支付",
    "cancelled": "已取消",
    "paid": "已支付",
    "in_progress": "进行中",
    "finished": "已结束",
}
ITEM_STATUS_DISPLAY = {
    "pending_payment": "待支付", "cancelled": "已取消", "paid": "已支付",
    "ticketed": "已出票", "refunded": "已退款", "completed": "已完成",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@registry.register("query_order_status")
def query_order_status(order_no: str | None = None, user_id: int | None = None, **_: Any) -> ActionResult:
    if not order_no:
        return ActionResult(ok=True, action="query_order_status",
                            text="请提供要查询的订单号（例如 ORD0000000001）。")
    order = fetch_one(
        """
        SELECT id, order_no, order_type_code, status_code, currency_code,
               goods_amount, payable_amount, paid_amount, paid_at, created_at
        FROM orders
        WHERE order_no = %s
        """,
        (order_no,),
    )
    if order is None:
        return ActionResult(ok=True, action="query_order_status",
                            text=f"没有查询到订单 {order_no}，请确认订单号是否正确。")
    items = fetch_all(
        "SELECT product_name, sale_amount FROM order_items WHERE order_id = %s",
        (order["id"],),
    )
    type_txt = ORDER_TYPE_DISPLAY.get(order["order_type_code"], order["order_type_code"])
    status_txt = ORDER_STATUS_DISPLAY.get(order["status_code"], order["status_code"])
    lines = [f"订单 {order['order_no']} 的信息如下："]
    lines.append(f"- 订单类型：{type_txt}")
    lines.append(f"- 订单状态：{status_txt}")
    for it in items:
        lines.append(f"- 预订产品：{it['product_name']}（¥{float(it['sale_amount']):,.2f}）")
    lines.append(f"- 应付金额：¥{float(order['payable_amount']):,.2f}")
    if order["paid_at"]:
        lines.append(f"- 支付时间：{format_datetime(order['paid_at'])}")
    return ActionResult(ok=True, action="query_order_status", text="\n".join(lines),
                        data={"order_no": order_no, "status": order["status_code"]})


@registry.register("query_trip_info")
def query_trip_info(
    target: str | None = None,
    order_no: str | None = None,
    user_id: int | None = None,
    **_: Any,
) -> ActionResult:
    target = target or order_no
    if not target:
        return ActionResult(ok=True, action="query_trip_info",
                            text="请提供订单号或出行日期，我来帮您查询出行信息。")

    # 按订单号查询
    if _DATE_RE.match(target):
        return _trip_info_by_date(target, user_id)
    return _trip_info_by_order(target)


def _trip_info_by_order(order_no: str) -> ActionResult:
    order = fetch_one(
        "SELECT id, order_no, status_code FROM orders WHERE order_no = %s",
        (order_no,),
    )
    if order is None:
        return ActionResult(ok=True, action="query_trip_info",
                            text=f"没有查询到订单 {order_no}，请确认订单号是否正确。")
    items = fetch_all(
        """
        SELECT oi.product_name, oi.product_type_code, oi.travel_time, oi.travel_end_time,
               oi.status_code, t.traveler_name
        FROM order_items oi
        LEFT JOIN travelers t ON t.id = oi.traveler_id
        WHERE oi.order_id = %s
        ORDER BY oi.travel_time ASC
        """,
        (order["id"],),
    )
    if not items:
        return ActionResult(ok=True, action="query_trip_info",
                            text=f"订单 {order_no} 暂无出行明细。")
    lines = [f"订单 {order_no} 的出行安排如下："]
    for it in items:
        time_txt = format_datetime(it["travel_time"]) or "—"
        end_txt = format_datetime(it["travel_end_time"])
        if end_txt and end_txt[:10] != time_txt[:10]:
            time_txt = f"{time_txt} 至 {end_txt}"
        lines.append(
            f"- {it['product_name']}，出行时间：{time_txt}"
            f"（入住人/出行人：{it['traveler_name'] or '—'}）"
        )
    return ActionResult(ok=True, action="query_trip_info", text="\n".join(lines),
                        data={"order_no": order_no, "items": items})


def _trip_info_by_date(day: str, user_id: int | None) -> ActionResult:
    if user_id is None:
        return ActionResult(ok=True, action="query_trip_info",
                            text="按日期查询出行安排需要绑定用户身份，您也可以直接提供订单号查询。")
    items = fetch_all(
        """
        SELECT oi.product_name, oi.travel_time, t.traveler_name, o.order_no
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        LEFT JOIN travelers t ON t.id = oi.traveler_id
        WHERE oi.user_id = %s AND DATE(oi.travel_time) = %s
        ORDER BY oi.travel_time ASC
        """,
        (user_id, day),
    )
    if not items:
        return ActionResult(ok=True, action="query_trip_info",
                            text=f"您在 {day} 当天没有出行安排。")
    lines = [f"您 {day} 的出行安排如下："]
    for it in items:
        lines.append(
            f"- {it['product_name']}（订单 {it['order_no']}），"
            f"出行时间 {format_datetime(it['travel_time'])}，出行人 {it['traveler_name'] or '—'}"
        )
    return ActionResult(ok=True, action="query_trip_info", text="\n".join(lines),
                        data={"items": items})
