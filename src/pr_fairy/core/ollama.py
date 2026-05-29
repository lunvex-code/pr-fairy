import shutil
import subprocess
from typing import Any

import httpx
from rich.console import Console
from rich.prompt import Confirm

from pr_fairy.core.model_recommender import (
    DEFAULT_LLM_MODEL,
    LLMModelRecommendation,
    get_llm_model_recommendations,
    print_llm_model_table,
)

console = Console()


def is_ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def start_ollama_if_needed() -> bool:
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=1.5)
        return r.status_code == 200
    except Exception:
        pass

    if is_ollama_installed():
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import time
            time.sleep(2.5)
            return True
        except Exception:
            return False
    return False


def get_installed_ollama_models() -> list[str]:
    """Return list of locally available model names."""
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=6)
        if resp.status_code == 200:
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    return []


# ------------------------------------------------------------------
# Smart LLM Model Selection (Option B)
# ------------------------------------------------------------------

def ensure_suitable_llm_model(preferred_tag: str | None = None, *, interactive: bool = True) -> str:
    """
    The heart of option B.

    When the user enables --llm mode, we check if they have a model that is
    actually good at following complex, strict instructions for micro-fixes.

    If not (or nothing is installed), we recommend the best lightweight models
    for this specific use case and offer to download one automatically.
    """
    installed = get_installed_ollama_models()

    # If user has a specific preference and it's installed, use it
    if preferred_tag and any(preferred_tag in m for m in installed):
        return preferred_tag

    # Check if any of the really good LLM models are installed
    good_models = get_llm_model_recommendations()

    for rec in good_models:
        if any(rec.tag in m or m.startswith(rec.tag.split(":")[0]) for m in installed):
            console.print(f"[green]✓[/green] Найдена хорошая модель для LLM-режима: [bold]{rec.tag}[/bold]")
            return rec.tag

    # Nothing suitable found → recommend and offer to install
    console.print("\n[yellow]⚠ Для режима --llm нужна модель, которая хорошо следует сложным инструкциям.[/yellow]\n")

    print_llm_model_table("Рекомендуемые модели специально для умных микро-правок")

    best = DEFAULT_LLM_MODEL

    if not interactive:
        console.print(f"\n[cyan]По умолчанию будет использована:[/cyan] [bold]{best.tag}[/bold]")
        return best.tag

    console.print(f"\n[bold]Рекомендую установить:[/bold] [green]{best.tag}[/green] — {best.why_good}")

    if Confirm.ask(f"\nСкачать модель {best.tag} сейчас? (~{best.size_gb:.1f} ГБ)", default=True):
        if not start_ollama_if_needed():
            console.print("[red]Не удалось запустить Ollama. Установи его и попробуй снова.[/red]")
            return best.tag

        success = _pull_model_with_progress(best.tag)
        if success:
            console.print(f"\n[bold green]✓ Модель {best.tag} успешно скачана![/bold green]")
            console.print("Теперь `fairy watch --llm` будет работать на хорошем уровне.\n")
            return best.tag
        else:
            console.print("[yellow]Не удалось скачать. Можно попробовать позже командой:[/yellow]")
            console.print(f"  ollama pull {best.tag}")
            return best.tag

    # User refused — let them pick manually or fall back
    console.print("\n[dim]Ты можешь выбрать модель вручную позже через `fairy models` или `--model`.[/dim]")
    return best.tag


def _pull_model_with_progress(tag: str) -> bool:
    """Pull model with nice progress output (re-uses logic similar to wizard)."""
    import time

    console.print(f"\n[cyan]⬇️  Скачиваю {tag}...[/cyan] (это может занять 5–15 минут)")

    try:
        process = subprocess.Popen(
            ["ollama", "pull", tag],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in process.stdout or []:
            line = line.strip()
            if line:
                # Show only meaningful progress lines
                if any(kw in line.lower() for kw in ["pulling", "downloading", "using", "success"]):
                    console.print(f"  {line}")

        process.wait()
        return process.returncode == 0

    except Exception as e:
        console.print(f"[red]Ошибка при скачивании: {e}[/red]")
        return False
