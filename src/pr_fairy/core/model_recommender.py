"""
Smart model recommender for PR Fairy's LLM micro-fix mode (--llm).

This is the core of option B: when the user wants intelligent fixes via the local model,
we automatically guide them to a model that is actually good at following strict instructions
and producing small, high-quality patches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.table import Table

console = Console()

LLMUseCase = Literal["micro_fixes", "general"]


@dataclass(frozen=True)
class LLMModelRecommendation:
    tag: str                    # Real Ollama tag, e.g. "qwen2.5-coder:7b"
    name: str
    size_gb: float
    ram_min_gb: int
    why_good: str               # Why this model is strong for LLM micro-fixes
    speed: str
    priority: int               # Lower = better default for --llm


# Best models for strict instruction following + tiny safe code/docs edits (as of 2025-2026)
LLM_RECOMMENDED_MODELS: list[LLMModelRecommendation] = [
    LLMModelRecommendation(
        tag="qwen2.5-coder:7b",
        name="Qwen2.5-Coder 7B",
        size_gb=4.7,
        ram_min_gb=8,
        why_good="Лучшая лёгкая модель для строгих инструкций и микро-правок в коде/документации. Отлично следует промптам.",
        speed="Быстро (40-70 т/с)",
        priority=1,
    ),
    LLMModelRecommendation(
        tag="gemma3:4b",
        name="Gemma 3 4B",
        size_gb=3.3,
        ram_min_gb=6,
        why_good="Отличное понимание инструкций при очень малом весе. Хороший выбор для слабых машин.",
        speed="Очень быстро",
        priority=2,
    ),
    LLMModelRecommendation(
        tag="qwen2.5:7b-instruct",
        name="Qwen2.5 7B Instruct",
        size_gb=4.5,
        ram_min_gb=8,
        why_good="Сильная общая модель с отличным следованием сложным правилам.",
        speed="Быстро",
        priority=3,
    ),
    LLMModelRecommendation(
        tag="phi4:mini",
        name="Phi-4 Mini",
        size_gb=2.8,
        ram_min_gb=6,
        why_good="Хорошее качество при ультра-малом размере. Подходит для ноутбуков.",
        speed="Очень быстро",
        priority=4,
    ),
    LLMModelRecommendation(
        tag="qwen2.5:3b-instruct",
        name="Qwen2.5 3B Instruct",
        size_gb=2.0,
        ram_min_gb=4,
        why_good="Самая лёгкая модель, которая всё ещё способна следовать строгим промптам.",
        speed="Молниеносно",
        priority=5,
    ),
]

DEFAULT_LLM_MODEL = LLM_RECOMMENDED_MODELS[0]  # qwen2.5-coder:7b is the sweet spot


def get_llm_model_recommendations() -> list[LLMModelRecommendation]:
    return sorted(LLM_RECOMMENDED_MODELS, key=lambda m: m.priority)


def print_llm_model_table(title: str = "Рекомендуемые модели для умного режима (--llm)"):
    """Beautiful table for the user when we need to recommend a model."""
    models = get_llm_model_recommendations()

    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Модель", style="green", no_wrap=True)
    table.add_column("Вес", style="yellow")
    table.add_column("RAM мин.", style="yellow")
    table.add_column("Почему хороша для PR Fairy", style="white")
    table.add_column("Скорость", style="dim")

    for m in models:
        star = "⭐ " if m.priority == 1 else ""
        table.add_row(
            f"{star}{m.tag}",
            f"{m.size_gb:.1f} ГБ",
            f"{m.ram_min_gb} ГБ",
            m.why_good,
            m.speed,
        )

    console.print(table)


def get_best_available_llm_model(installed_models: list[str]) -> LLMModelRecommendation | None:
    """Among installed models, pick the best one for LLM micro-fixes."""
    for rec in get_llm_model_recommendations():
        for installed in installed_models:
            if rec.tag in installed or installed.startswith(rec.tag.split(":")[0]):
                return rec
    return None


def is_model_suitable_for_llm(tag: str, installed: list[str]) -> bool:
    """Heuristic: is the currently configured model decent for strict LLM tasks?"""
    good_tags = [m.tag for m in LLM_RECOMMENDED_MODELS]

    # Direct match
    if any(tag == g or tag.startswith(g.split(":")[0]) for g in good_tags):
        return True

    # If user has something reasonably new and >3B, we allow it
    if any(x in tag.lower() for x in ["qwen", "gemma", "phi", "mistral", "llama3"]):
        return True

    return False
