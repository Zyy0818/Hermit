from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hermit.plugins.hooks_engine import HooksEngine
from hermit.plugins.rules import load_rules_text
from hermit.plugins.skills import SkillDefinition, load_skills


@dataclass
class PluginSnapshot:
    skills: list[SkillDefinition]
    rules_text: str


class PluginManager:
    def __init__(self, skills_dir: Path, rules_dir: Path) -> None:
        self.skills_dir = skills_dir
        self.rules_dir = rules_dir
        self.hooks = HooksEngine()

    def load(self) -> PluginSnapshot:
        return PluginSnapshot(
            skills=load_skills(self.skills_dir),
            rules_text=load_rules_text(self.rules_dir),
        )
