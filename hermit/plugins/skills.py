from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class SkillDefinition:
    name: str
    description: str
    path: Path


def load_skills(skills_dir: Path) -> list[SkillDefinition]:
    if not skills_dir.exists():
        return []

    skills: list[SkillDefinition] = []
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        content = path.read_text(encoding="utf-8").strip()
        first_line = next((line.strip("# ").strip() for line in content.splitlines() if line.strip()), "")
        skills.append(
            SkillDefinition(
                name=path.parent.name,
                description=first_line or "No description",
                path=path,
            )
        )
    return skills
