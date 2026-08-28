"""工单提交 Action。"""

from __future__ import annotations

from typing import Any

from ...database import db_cursor, fetch_one
from ...utils import local_now, make_no
from .base import ActionResult, registry

TICKET_TYPE_DISPLAY = {
    "after_sale": "售后",
    "complaint": "投诉",
    "refund": "退款",
}


@registry.register("submit_ticket")
def submit_ticket(
    ticket_type: str | None = None,
    order_no: str | None = None,
    problem_desc: str | None = None,
    user_id: int | None = None,
    session_id: str | None = None,
    **_: Any,
) -> ActionResult:
    if not ticket_type:
        return ActionResult(ok=True, action="submit_ticket",
                            text="请问您需要提交哪类工单？（售后 / 投诉 / 退款）")
    if not problem_desc:
        return ActionResult(ok=True, action="submit_ticket",
                            text="请简单描述一下您遇到的问题。")

    now = local_now()
    order_no_value = (order_no or "").strip() or None
    with db_cursor() as (_, cursor):
        cursor.execute(
            """
            INSERT INTO service_tickets (
                ticket_no, user_id, ticket_type_code, order_no, description,
                status_code, session_id, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s)
            """,
            (make_no("TK"), user_id, ticket_type, order_no_value, problem_desc,
             session_id, now, now),
        )
        ticket_id = cursor.lastrowid

    row = fetch_one("SELECT ticket_no, ticket_type_code FROM service_tickets WHERE id = %s", (ticket_id,))
    type_txt = TICKET_TYPE_DISPLAY.get(ticket_type, ticket_type)
    text = (
        f"工单已提交成功：\n"
        f"- 工单编号：{row['ticket_no']}\n"
        f"- 工单类型：{type_txt}\n"
        f"- 关联订单：{order_no_value or '无'}\n"
        f"- 处理预期：我们会在 24 小时内由客服专员跟进处理，请保持手机畅通。"
    )
    return ActionResult(ok=True, action="submit_ticket", text=text,
                        data={"ticket_no": row["ticket_no"], "ticket_type": ticket_type})
