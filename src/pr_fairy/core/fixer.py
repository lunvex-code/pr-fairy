"""
Base definitions for micro-fixes used by both static detectors and LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProposedFix:
    """Represents one small, safe change that PR Fairy wants to make."""

    file_path: Path
    description: str
    diff: str
    confidence: float
    category: str
    line_start: int
    line_end: int

    # Optional: for reliable direct application (preferred over diff)
    old_text: str | None = None
    new_text: str | None = None
