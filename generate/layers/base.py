"""数据生成器基类。"""

from abc import ABC, abstractmethod

from ..config import LAYERS
from ..progress import (
    complete_progress_tasks,
    console_print,
    is_table_completed,
    reset_progress_tasks,
)


class BaseGenerator(ABC):
    """数据生成器基类。"""

    layer: int = 0
    layer_name: str = ""

    def log(self, message: str) -> None:
        console_print(message)

    def header(self) -> None:
        reset_progress_tasks()
        name = self.layer_name or LAYERS[self.layer]["name"]
        console_print(f"\n{'=' * 64}")
        console_print(f"Layer {self.layer}: {name}")
        console_print(f"{'=' * 64}")

    def log_table_counts(self, counts: dict[str, int]) -> None:
        for table in LAYERS[self.layer]["tables"]:
            if not is_table_completed(table):
                console_print(f"  [OK] {table}: {counts.get(table, 0)} rows")
        complete_progress_tasks()

    @abstractmethod
    def run(self) -> None:
        """执行数据生成。"""
