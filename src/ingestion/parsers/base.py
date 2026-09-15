"""Parser abstraction and base classes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ParsedDocument:
    """Result of parsing a file."""

    text: str
    metadata: dict[str, Any]
    sections: list[Section] | None = None

    def __post_init__(self):
        if self.sections is None:
            self.sections = []


@dataclass
class Section:
    """A logical section within a document."""

    heading: str | None
    level: int
    content: str
    metadata: dict[str, Any] | None = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseParser(ABC):
    """Abstract base class for document parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """File extensions this parser handles (e.g., {'.md', '.markdown'})."""

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """Parse a file and return structured document."""

    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return path.suffix.lower() in self.supported_extensions
