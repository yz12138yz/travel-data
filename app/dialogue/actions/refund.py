"""退款申请 Action。"""

from __future__ import annotations

from typing import Any

from ...database import db_cursor, fetch_all, fetch_one
from ...utils import local_now, make_no
from .base import ActionResult, registry

REFUND_TYPE_DISPLAY = {"full": "全额退款", "partial": "部分退款"}


@registry.register("apply_refund")
def apply_refund(
    order_no: str | None = None,
    refund_reason: str | None = None,
    refund_type: str | None = None,
    user_id: int | None = None,
    **_: Any,
) -> ActionResult:
    if not order_no:
        return ActionResult(ok=True, action="apply_refund",
                            text="请提供需要退款的订单号。")
    order = fetch_one(
        "SELECT id, user_id, order_no FROM orders WHERE order_no = %s",
        (order_no,),
    )
    if order is None:
        return ActionResult(ok=True, action="apply_refund",
                            text=f"没有查询到订单 {order_no}，请确认订单号是否正确。")
    # 找可退款的订单明细（状态允许且仍有剩余可退金额）
    items = fetch_all(
        """
        SELECT oi.id, oi.product_name, oi.sale_amount,
               COALESCE((
                   SELECT SUM(rr.amount) FROM refund_records rr
                   WHERE rr.order_item_id = oi.id AND rr.status_code = 'success'
               ), 0) AS refunded
        FROM order_items oi
        WHERE oi.order_id = %s
          AND oi.status_code IN ('paid', 'ticketed', 'completed')
        """,
        (order["id"],),
    )
    refundable = [it for it in items if float(it["sale_amount"]) - float(it["refunded"]) > 0]
    if not refundable:
        return ActionResult(ok=True, action="apply_refund",
                            text=f"订单 {order_no} 当前没有可退款的明细。")
    item = refundable[0]
    amount = round(float(item["sale_amount"]) - float(item["refunded"]), 2)

    now = local_now()
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO refund_requests (
                refund_request_no, order_id, order_item_id, user_id, requested_amount,
                approved_amount, status_code, requested_at, processed_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, NULL, 'pending', %s, NULL, %s, %s)
            """,
            (make_no("RR"), order["id"], item["id"], order["user_id"], amount, now, now, now),
        )
        refund_request_id = cursor.lastrowid

    row = fetch_one(
        "SELECT refund_request_no, requested_amount, status_code FROM refund_requests WHERE id = %s",
        (refund_request_id,),
    )
    type_txt = REFUND_TYPE_DISPLAY.get(refund_type or "full", refund_type or "全额退款")
    reason_txt = refund_reason or "未填写"
    text = (
        f"退款申请已提交：\n"
        f"- 申请单号：{row['refund_request_no']}\n"
        f"- 退款类型：{type_txt}\n"
        f"- 退款金额：¥{float(row['requested_amount']):,.2f}\n"
        f"- 退款原因：{reason_txt}\n"
        f"- 当前状态：待处理，审核通过后将原路退回，一般 1-3 个工作日到账。"
    )
    return ActionResult(ok=True, action="apply_refund", text=text,
                        data={"refund_request_no": row["refund_request_no"],
                              "amount": float(row["requested_amount"])})
