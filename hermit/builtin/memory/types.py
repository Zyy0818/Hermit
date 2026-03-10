from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


DEFAULT_CATEGORIES = [
    "用户偏好",
    "项目约定",
    "技术决策",
    "环境与工具",
    "其他",
    "进行中的任务",
]


@dataclass
class MemoryEntry:
    category: str
    content: str
    score: int = 5
    locked: bool = False
    created_at: date = field(default_factory=date.today)

    def render(self) -> str:
        lock = "🔒" if self.locked else ""
        return f"- [{self.created_at.isoformat()}] [s:{self.score}{lock}] {self.content}"
