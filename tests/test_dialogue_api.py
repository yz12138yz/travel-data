"""对话系统接口集成测试。

依赖已初始化的 travel 数据库（执行 ``make smoke`` 或 ``make gen``）。
覆盖：会话创建、状态持久化 / 会话恢复、订单查询、产品咨询、
退款申请与工单提交的端到端闭环。
"""

from __future__ import annotations

from app.database import fetch_all, fetch_one

API = "/api/dialogue"


def _first_order_no() -> str:
    row = fetch_one("SELECT order_no FROM orders ORDER BY id LIMIT 1")
    assert row is not None, "数据库未初始化或无订单数据，请先执行 make smoke"
    return row["order_no"]


def _refundable_order_no() -> str:
    row = fetch_one(
        """
        SELECT o.order_no
        FROM orders o
        JOIN order_items oi
          ON oi.order_id = o.id
         AND oi.status_code IN ('paid', 'ticketed', 'completed')
        WHERE o.status_code IN ('paid', 'in_progress', 'finished')
        ORDER BY o.id
        LIMIT 1
        """
    )
    assert row is not None, "数据库无可用退款订单，请先执行 make smoke"
    return row["order_no"]


def _hotel_search_city() -> str:
    row = fetch_one(
        """
        SELECT a.area_name
        FROM hotels h
        JOIN areas a ON a.id = h.area_id
        WHERE h.status_code = 'active'
        ORDER BY h.id
        LIMIT 1
        """
    )
    assert row is not None, "数据库无酒店数据，请先执行 make smoke"
    return row["area_name"]


def _create_session(client) -> str:
    resp = client.post(f"{API}/sessions", json={})
    assert resp.status_code == 200
    return resp.json()["sessionId"]


def test_create_session_and_state(client):
    session_id = _create_session(client)
    resp = client.get(f"{API}/sessions/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessionId"] == session_id
    assert data["state"]["currentTask"] is None


def test_greet_and_persistence(client):
    session_id = _create_session(client)
    resp = client.post(f"{API}/sessions/{session_id}/messages", json={"content": "你好"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"]["content"]

    # 会话恢复：历史消息包含用户与助手各一条
    history = client.get(f"{API}/sessions/{session_id}/messages").json()
    roles = [m["role"] for m in history["messages"]]
    assert "user" in roles and "assistant" in roles


def test_order_status_query(client):
    order_no = _first_order_no()
    session_id = _create_session(client)
    resp = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": f"帮我查下订单 {order_no}"},
    )
    assert resp.status_code == 200
    reply = resp.json()["reply"]["content"]
    assert order_no in reply


def test_trip_info_query(client):
    order_no = _first_order_no()
    session_id = _create_session(client)
    resp = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": f"我的订单 {order_no} 的出行信息"},
    )
    assert resp.status_code == 200
    reply = resp.json()["reply"]["content"]
    assert order_no in reply or "出行" in reply


def test_product_consult(client):
    city = _hotel_search_city()
    session_id = _create_session(client)
    resp = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": f"{city}有哪些酒店"},
    )
    assert resp.status_code == 200
    reply = resp.json()["reply"]["content"]
    assert "酒店" in reply


def test_refund_full_flow(client):
    order_no = _refundable_order_no()
    session_id = _create_session(client)

    r1 = client.post(f"{API}/sessions/{session_id}/messages", json={"content": "我要退款"})
    assert "订单号" in r1.json()["reply"]["content"]

    r2 = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": order_no},
    )
    assert "原因" in r2.json()["reply"]["content"]

    r3 = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": "行程变更，全额退款"},
    )
    reply = r3.json()["reply"]["content"]
    assert "退款申请已提交" in reply

    # 校验退款申请已落库
    refund_no = [line for line in reply.split("\n") if "申请单号" in line][0]
    refund_no = refund_no.split("：")[-1].strip()
    row = fetch_one(
        "SELECT id FROM refund_requests WHERE refund_request_no = %s", (refund_no,)
    )
    assert row is not None


def test_ticket_full_flow(client):
    session_id = _create_session(client)

    r1 = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": "酒店房间和预订时描述的不一样，我要投诉"},
    )
    assert "订单号" in r1.json()["reply"]["content"]

    r2 = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": "无"},
    )
    assert "描述" in r2.json()["reply"]["content"]

    r3 = client.post(
        f"{API}/sessions/{session_id}/messages",
        json={"content": "房间有异味，与页面描述不符"},
    )
    reply = r3.json()["reply"]["content"]
    assert "工单已提交" in reply

    ticket_no = [line for line in reply.split("\n") if "工单编号" in line][0]
    ticket_no = ticket_no.split("：")[-1].strip()
    row = fetch_one(
        "SELECT id FROM service_tickets WHERE ticket_no = %s", (ticket_no,)
    )
    assert row is not None


def test_stream_response(client):
    session_id = _create_session(client)
    resp = client.post(
        f"{API}/sessions/{session_id}/messages/stream",
        json={"content": "你好"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "data:" in body
    assert "[DONE]" in body
