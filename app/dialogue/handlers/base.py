"""处理器基础模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HandlerResult:
    """处理器执行结果。"""

    reply: str
    intent: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
