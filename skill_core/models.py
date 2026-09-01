from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class SkillMetadata:
    """Level 1 metadata kept in the registry."""

    name: str
    description: str
    author: Optional[str] = None
    version: Optional[str] = None


@dataclass
class Skill:
    """Full skill payload with its resolved base path."""

    metadata: SkillMetadata
    content: str
    base_path: Path
    references: Dict[str, str] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.metadata.name
