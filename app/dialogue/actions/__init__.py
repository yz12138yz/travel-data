"""自定义 Action（业务查询）。

对应电商小二「附录 - 自定义 Action 实现」。

每个 Action 是一个可调用对象，负责对接 travel 数据库完成一次业务操作
（查询产品 / 查询订单 / 查询出行信息 / 创建退款申请 / 创建工单），
并返回自然语言回复与结构化数据。Action 通过 ``ActionRegistry`` 注册，
任务流程 / 产品咨询处理器按名调用，便于扩展。
"""

from .base import ActionResult, ActionRegistry, registry, run_action
from . import products, orders, refund, ticket  # noqa: F401  # 触发注册

__all__ = [
    "ActionResult",
    "ActionRegistry",
    "registry",
    "run_action",
    "products",
    "orders",
    "refund",
    "ticket",
]
