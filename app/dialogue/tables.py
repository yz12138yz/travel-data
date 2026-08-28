"""对话系统所需的表结构（独立于「问数」核心业务表）。

说明：travel 数据库由 ``sql/travel.sql`` 负责建表，本模块新增的表不纳入
该脚本，而是由对话服务在启动时以 ``CREATE TABLE IF NOT EXISTS`` 幂等创建，
避免影响既有「问数」项目的建表 / 初始化流程。
"""

from __future__ import annotations

import threading

from ..database import execute

_DDL = """
CREATE TABLE IF NOT EXISTS dialogue_sessions (
    id VARCHAR(64) NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    state_json JSON NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    KEY idx_dialogue_sessions_user (user_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '对话会话（持久化对话状态）';

CREATE TABLE IF NOT EXISTS dialogue_messages (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role VARCHAR(20) NOT NULL COMMENT '消息角色：user=用户，assistant=客服',
    content TEXT NOT NULL,
    intent VARCHAR(50) NULL COMMENT '该消息识别出的意图',
    trace_json JSON NULL COMMENT '处理轨迹（可观测性）',
    created_at DATETIME NOT NULL,
    KEY idx_dialogue_messages_session (session_id, id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '对话消息';

CREATE TABLE IF NOT EXISTS service_tickets (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ticket_no VARCHAR(50) NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    ticket_type_code VARCHAR(30) NOT NULL COMMENT '工单类型：after_sale=售后，complaint=投诉，refund=退款',
    order_no VARCHAR(50) NULL COMMENT '关联订单号，可为空',
    description TEXT NOT NULL COMMENT '问题描述',
    status_code VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '状态：pending=待处理，processing=处理中，resolved=已解决',
    session_id VARCHAR(64) NULL COMMENT '来源会话 ID（审计追溯）',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_service_tickets_no (ticket_no),
    KEY idx_service_tickets_user (user_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = '客服工单';
"""

_lock = threading.Lock()
_ensured = False


def ensure_tables() -> None:
    """幂等创建对话系统所需的表。"""
    global _ensured
    if _ensured:
        return
    with _lock:
        if _ensured:
            return
        for statement in _DDL.split(";"):
            statement = statement.strip()
            if statement:
                execute(statement)
        _ensured = True
