"""
High-level LLM-powered micro-fix engine.

This module is responsible for safely asking the local model for fixes
and validating the results before they are shown or applied.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from pr_fairy.core.fixer import ProposedFix
from pr_fairy.core.llm import FairyLLM, LLMSuggestion, get_llm

console = Console()


class LLMMicroFixer:
    """
    Uses the local LLM to find additional high-quality micro-fixes
    that the static detectors would miss (mainly typos in comments and docs).
    """

    INTERESTING_FILES = (
        "README", "CHANGELOG", "CONTRIBUTING", "docs/", ".md", "comments", "docstring"
    )

    def __init__(self, model: str | None = None):
        # auto_select_for_llm=True triggers the smart recommender (Option B)
        self.llm: FairyLLM = get_llm(model, auto_select_for_llm=True)

    def find_llm_fixes(
        self,
        repo_root: Path,
        max_files_to_ask: int = 6,
        max_suggestions: int = 3,
    ) -> list[ProposedFix]:
        """
        Scan interesting files in the repo and ask the LLM for safe micro-fixes.
        Returns a list of ProposedFix objects that can be used by the rest of the system.
        """
        suggestions: list[ProposedFix] = []

        candidates = self._find_interesting_files(repo_root, max_files_to_ask)

        for file_path in candidates:
            suggestion = self.llm.suggest_for_file(file_path, repo_root)
            if not suggestion:
                continue

            # Convert LLM suggestion into our standard ProposedFix format
            fix = self._suggestion_to_proposed_fix(suggestion, repo_root)
            if fix:
                suggestions.append(fix)
                if len(suggestions) >= max_suggestions:
                    break

        return suggestions

    def _find_interesting_files(self, repo_root: Path, limit: int) -> list[Path]:
        """Find files that are worth sending to the LLM (prefer prose-heavy files)."""
        interesting: list[Path] = []
        seen = set()

        # Highest priority: pure documentation
        doc_patterns = [
            "README*", "CHANGELOG*", "CONTRIBUTING*", "HISTORY*",
            "docs/**/*.md", "**/docs/**/*.md", "*.md",
        ]

        for pattern in doc_patterns:
            for path in sorted(repo_root.glob(pattern), key=lambda p: len(str(p))):
                if len(interesting) >= limit:
                    break
                if not path.is_file() or path in seen:
                    continue
                if any(x in path.parts for x in ["node_modules", "vendor", "dist", ".venv", "build"]):
                    continue
                seen.add(path)
                interesting.append(path)

        # Then source files that are likely to have good comments/docstrings
        if len(interesting) < limit:
            for pattern in ["src/**/*.py", "app/**/*.py", "lib/**/*.py", "**/*.py"]:
                for path in repo_root.glob(pattern):
                    if len(interesting) >= limit:
                        break
                    if not path.is_file() or path in seen:
                        continue
                    if any(x in path.parts for x in ["test", "tests", "node_modules", "vendor"]):
                        continue
                    # Prefer files that are not too code-heavy (heuristic)
                    try:
                        text = path.read_text(encoding="utf-8", errors="ignore")
                        if text.count("#") + text.count('"""') + text.count("'''") > 3:
                            seen.add(path)
                            interesting.append(path)
                    except Exception:
                        continue

        return interesting[:limit]

    def _suggestion_to_proposed_fix(
        self,
        suggestion: LLMSuggestion,
        repo_root: Path,
    ) -> ProposedFix | None:
        """Convert an LLM suggestion into a ProposedFix with extra safety."""

        if not suggestion.file_path or not suggestion.diff.strip():
            return None

        # Extra paranoia: the diff must be small
        if suggestion.diff.count("\n") > 9:
            return None

        return ProposedFix(
            file_path=suggestion.file_path,
            description=f"[LLM] {suggestion.reason}",
            diff=suggestion.diff,
            confidence=min(suggestion.confidence, 0.91),  # cap LLM confidence a bit
            category="llm",
            line_start=1,
            line_end=1,
            old_text=None,   # LLM gives us diff, not direct text
            new_text=None,
        )

    def close(self):
        self.llm.close()


def find_llm_fixes(repo_root: Path, **kwargs) -> list[ProposedFix]:
    """Convenience function."""
    fixer = LLMMicroFixer()
    try:
        return fixer.find_llm_fixes(repo_root, **kwargs)
    finally:
        fixer.close()
