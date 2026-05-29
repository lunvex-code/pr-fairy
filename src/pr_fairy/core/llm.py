"""
LLM client specialized for tiny, extremely safe micro-fixes.

This is the "brain" of PR Fairy when --llm flag is used.

Design principles:
- The model must be ultra-conservative.
- Prefer saying "no change" over risking a bad suggestion.
- Only suggest changes that are obviously correct even to a junior developer.
- Diffs must be tiny (ideally 1-4 lines changed).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from rich.console import Console

from pr_fairy.core.config import load_config
from pr_fairy.core.ollama import start_ollama_if_needed

console = Console()


# This prompt is carefully engineered for strong instruction-following models (Qwen2.5-Coder, Gemma3, etc.)
# Goal: find tiny, obviously correct improvements that any senior developer would accept without hesitation.

SYSTEM_PROMPT = """Ты — PR Fairy, крайне осторожная ночная фея-кодер 2026 года.

Ты находишь **только** крошечные, очевидные и абсолютно безопасные улучшения. Лучше отказаться от правки, чем сделать сомнительную.

### РАЗРЕШЁННЫЕ типы правок (только эти!):

1. **Опечатки в естественном языке**
   - В комментариях, docstring, README, CONTRIBUTING, CHANGELOG, markdown-документации
   - Примеры: "recieve" → "receive", "teh project" → "the project", "folow these steps" → "follow these steps"

2. **Мелкие улучшения читаемости в текстах**
   - Удаление двойных пробелов между словами
   - Удаление лишних пустых строк внутри секций
   - Исправление очевидных мелких стилистических проблем в списках и заголовках

3. **Очевидные улучшения в комментариях и документации**
   - Удаление устаревших/ложных комментариев (например "TODO: delete this later" который висит годами)
   - Небольшие уточнения в описаниях, которые делают текст точнее

### СТРОГО ЗАПРЕЩЕНО:

- Любые правки в executable коде (Python, JS, TS, Go и т.д.), даже в комментариях к сложному коду
- Изменение импортов, названий, логики, структуры
- Правки в файлах тестов
- Удаление кода или строк, которые могут иметь смысл
- Всё, что требует понимания контекста больше одной функции/секции

### ПРАВИЛА ОТВЕТА:

- Если есть **хоть малейшее сомнение** — отвечай `no_change`
- Diff должен быть **минимальным** (максимум 3-4 строки изменений)
- Reason должен быть очень коротким и точным

Отвечай **исключительно** в формате JSON без какого-либо другого текста:

{
  "action": "suggest_patch" | "no_change",
  "reason": "Короткое объяснение на русском (максимум 7 слов)",
  "confidence": 0.80-1.0,
  "diff": "полноценный маленький unified diff"
}
"""


@dataclass
class LLMSuggestion:
    action: str
    reason: str
    confidence: float
    diff: str
    file_path: Path | None = None


class FairyLLM:
    """Client for asking the local model for extremely conservative micro-fixes."""

    def __init__(self, model: str | None = None, *, auto_select_for_llm: bool = True):
        cfg = load_config()
        raw_model = model or cfg.model

        # Smart model selection for --llm mode (Option B)
        if auto_select_for_llm:
            from pr_fairy.core.ollama import ensure_suitable_llm_model
            self.model = ensure_suitable_llm_model(raw_model)
        else:
            self.model = raw_model

        self.host = cfg.ollama_host.rstrip("/")
        self.client = httpx.Client(timeout=180.0)

    def _ensure_server(self) -> bool:
        return start_ollama_if_needed()

    def suggest_for_file(
        self,
        file_path: Path,
        repo_root: Path,
        content: str | None = None,
        max_lines: int = 180,
    ) -> LLMSuggestion | None:
        """
        Ask the model for one tiny safe fix in this specific file.
        Returns None if the model refuses or the suggestion is too risky.
        """
        if not self._ensure_server():
            return None

        if content is None:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return None

        # Truncate very large files
        lines = content.splitlines()
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines]) + "\n... (file truncated for analysis)"

        rel_path = str(file_path.relative_to(repo_root))

        user_prompt = f"""Файл: {rel_path}

Содержимое файла:
```
{content}
```

Проанализируй файл согласно своим строгим правилам и верни ТОЛЬКО JSON."""

        try:
            resp = self.client.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "system": SYSTEM_PROMPT,
                    "prompt": user_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.05,      # Extremely low creativity
                        "top_p": 0.8,
                        "num_predict": 450,
                        "repeat_penalty": 1.15,
                    },
                    "format": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "").strip()

            # Clean possible markdown code fences
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.lower().startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            parsed: dict[str, Any] = json.loads(raw)

            if parsed.get("action") != "suggest_patch":
                return None

            confidence = float(parsed.get("confidence", 0.0))
            diff = parsed.get("diff", "").strip()
            reason = parsed.get("reason", "")

            # === Strong post-validation (critical for safety) ===
            if not _is_valid_llm_suggestion(diff, reason, confidence):
                return None

            return LLMSuggestion(
                action="suggest_patch",
                reason=reason or "Модель предложила правку",
                confidence=confidence,
                diff=diff,
                file_path=file_path,
            )

        except Exception as e:
            # Silent fail is intentional — LLM is best effort
            if "debug" in str(e).lower():
                console.print(f"[dim red]LLM error: {e}[/dim red]")
            return None

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass


def get_llm(model: str | None = None, *, auto_select_for_llm: bool = True) -> FairyLLM:
    return FairyLLM(model, auto_select_for_llm=auto_select_for_llm)


# ------------------------------------------------------------------
# Safety validation for LLM suggestions
# ------------------------------------------------------------------

def _is_valid_llm_suggestion(diff: str, reason: str, confidence: float) -> bool:
    """Extra layer of defense after the model answers."""
    if confidence < 0.82:
        return False
    if not diff or len(diff) < 20:
        return False
    if len(diff) > 900:
        return False
    if diff.count("\n") > 10:
        return False

    # Disallow dangerous patterns
    dangerous = [
        "def ", "class ", "import ", "from ", "return ", "if __name__",
        "TODO", "FIXME", "raise ", "assert ", "@", "self.", "this.",
    ]
    lower_diff = diff.lower()
    for pat in dangerous:
        if pat.lower() in lower_diff:
            # Allow only if it's clearly inside a comment
            if not any(c in diff for c in ["#", "//", "/*", "\"", "'"]):
                return False

    # The diff must look like a real unified diff
    if not ("diff --git" in diff or "@@" in diff or "---" in diff):
        # Some models output just the changed lines — allow small ones
        if diff.count("+") + diff.count("-") < 1:
            return False

    # Reason must be meaningful
    if len(reason) < 4:
        return False

    return True
