"""处理器集合。

- ``TaskHandler``      —— 任务型对话（槽位收集 + 执行 Action）
- ``KnowledgeHandler`` —— 知识库 / FAQ / 政策检索
- ``ChitchatHandler``  —— 闲聊兜底
"""

from .base import HandlerResult
from .task import TaskHandler, TASK_FLOWS
from .knowledge import KnowledgeHandler
from .chitchat import ChitchatHandler

__all__ = [
    "HandlerResult",
    "TaskHandler",
    "TASK_FLOWS",
    "KnowledgeHandler",
    "ChitchatHandler",
]
