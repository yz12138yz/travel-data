"""DialogueStateRepository 实现。

对应电商小二「05 - DialogueStateRepository 实现」。

负责对话状态的持久化：将 ``DialogueState`` 序列化到数据库，支持
会话创建、状态保存 / 加载（会话恢复）、消息历史与执行轨迹记录。
"""

from __future__ import annotations

import json
from typing import Any

from ..database import db_cursor, fetch_all, fetch_one
from ..utils import local_now, make_no
from .state import DialogueState
from .tables import ensure_tables


class DialogueStateRepository:
    """对话状态仓库。"""

    def create_session(self, user_id: int | None = None) -> str:
        ensure_tables()
        session_id = make_no("S")
        state = DialogueState(session_id=session_id, user_id=user_id,
                              updated_at=local_now().isoformat())
        self.save_state(state)
        return session_id

    def save_state(self, state: DialogueState) -> None:
        ensure_tables()
        state.updated_at = local_now().isoformat()
        payload = json.dumps(state.to_dict(), ensure_ascii=False)
        now = local_now()
        with db_cursor() as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO dialogue_sessions (id, user_id, state_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    user_id = VALUES(user_id), state_json = VALUES(state_json), updated_at = VALUES(updated_at)
                """,
                (state.session_id, state.user_id, payload, now, now),
            )

    def load_state(self, session_id: str) -> DialogueState | None:
        ensure_tables()
        row = fetch_one(
            "SELECT user_id, state_json FROM dialogue_sessions WHERE id = %s",
            (session_id,),
        )
        if row is None:
            return None
        data = json.loads(row["state_json"]) if isinstance(row["state_json"], str) else row["state_json"]
        state = DialogueState.from_dict(data)
        state.session_id = session_id
        if state.user_id is None and row.get("user_id"):
            state.user_id = row["user_id"]
        return state

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        trace: list[Any] | None = None,
    ) -> None:
        ensure_tables()
        trace_json = json.dumps([t.to_dict() if hasattr(t, "to_dict") else t for t in (trace or [])],
                                ensure_ascii=False)
        now = local_now()
        with db_cursor() as (conn, cursor):
            cursor.execute(
                """
                INSERT INTO dialogue_messages (session_id, role, content, intent, trace_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (session_id, role, content, intent, trace_json, now),
            )

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        ensure_tables()
        return fetch_all(
            """
            SELECT role, content, intent, created_at
            FROM dialogue_messages
            WHERE session_id = %s
            ORDER BY id ASC
            """,
            (session_id,),
        )
