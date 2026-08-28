"""KnowledgeHandler 实现。

对应电商小二「08 - KnowledgeHandler 实现」。

负责 FAQ / 政策 / 预订规则等相对固定的知识性问答，按关键词检索知识库，
返回最匹配的答案；命中失败时给出引导话术。
"""

from __future__ import annotations

from typing import Any

from .. import knowledge
from ..intent import IntentResult
from .base import HandlerResult


class KnowledgeHandler:
    """知识库处理器。"""

    def handle(self, text: str, _intent_result: IntentResult | None = None) -> HandlerResult:
        result = knowledge.retrieve(text)
        return HandlerResult(
            reply=result.answer,
            intent="knowledge",
            data={"found": result.found, "category": result.category,
                  "matched": result.matched_keywords},
        )
