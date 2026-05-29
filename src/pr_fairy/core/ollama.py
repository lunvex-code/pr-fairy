import shutil
import subprocess
from typing import Any

import httpx
import questionary
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
    """Try to ensure Ollama server is running. More robust version."""
    # First quick check
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=1.2)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    if not is_ollama_installed():
        return False

    # Try to start it
    try:
        # On macOS, Ollama is often started via the app. 
        # We still try `ollama serve` as fallback.
        proc = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        # Give it time to boot
        import time
        for _ in range(6):  # up to ~6 seconds
            time.sleep(1.0)
            try:
                r = httpx.get("http://localhost:11434/api/tags", timeout=1.0)
                if r.status_code == 200:
                    return True
            except Exception:
                continue

        # Final check
        r = httpx.get("http://localhost:11434/api/tags", timeout=1.5)
        return r.status_code == 200

    except Exception:
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

    # === Interactive selection (what the user asked for) ===
    good_models = get_llm_model_recommendations()
    installed = get_installed_ollama_models()

    choices = []
    model_map = {}  # label -> recommendation

    for rec in good_models:
        already_installed = any(
            rec.tag in m or m.startswith(rec.tag.split(":")[0]) for m in installed
        )
        status = " ✓ уже установлена" if already_installed else ""

        label = f"{rec.tag}  (~{rec.size_gb:.1f} ГБ) — {rec.why_good[:55]}...{status}"
        choices.append(label)
        model_map[label] = rec

    choices.append("Пропустить (выбрать модель позже)")

    selected = questionary.select(
        "Выбери модель (стрелки ↑↓, Enter):",
        choices=choices,
        default=choices[0],  # top recommendation
    ).ask()

    if not selected or "Пропустить" in selected:
        console.print("\n[dim]Хорошо, модель можно скачать позже командой: [bold]fairy models[/bold] или при следующем `fairy watch --llm`[/dim]")
        return best.tag

    chosen_rec = model_map[selected]

    # If already installed, just return it
    if any(chosen_rec.tag in m or m.startswith(chosen_rec.tag.split(":")[0]) for m in installed):
        console.print(f"\n[green]✓ Модель {chosen_rec.tag} уже установлена[/green]")
        return chosen_rec.tag

    # Ask to download the chosen one
    if Confirm.ask(f"\nСкачать модель {chosen_rec.tag} сейчас? (~{chosen_rec.size_gb:.1f} ГБ)", default=True):
        if not is_ollama_installed():
            console.print("\n[yellow]Ollama не установлен.[/yellow]")
            if Confirm.ask("Установить Ollama автоматически сейчас?", default=True):
                success = _install_ollama()
                if not success:
                    console.print("[red]Не удалось установить Ollama автоматически.[/red]")
                    console.print("Установи вручную: https://ollama.com")
                    return chosen_rec.tag

        if not start_ollama_if_needed():
            console.print("\n[red]Не удалось запустить Ollama сервер.[/red]")
            console.print("Попробуй:")
            console.print("  • Открой приложение Ollama (macOS)")
            console.print("  • Выполни в терминале: [bold]ollama serve[/bold]")
            return chosen_rec.tag

        success = _pull_model_with_progress(chosen_rec.tag)
        if success:
            console.print(f"\n[bold green]✓ Модель {chosen_rec.tag} успешно скачана![/bold green]")
            console.print("Теперь `fairy watch --llm` будет работать на хорошем уровне.\n")
            return chosen_rec.tag
        else:
            console.print("[yellow]Не удалось скачать. Можно попробовать позже командой:[/yellow]")
            console.print(f"  ollama pull {chosen_rec.tag}")
            return chosen_rec.tag

    # User refused the chosen one
    console.print("\n[dim]Хорошо, модель можно скачать позже.[/dim]")
    return chosen_rec.tag


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


def _install_ollama() -> bool:
    """Attempt to install Ollama using the official one-liner."""
    import platform
    import subprocess

    system = platform.system().lower()
    console.print("[cyan]Устанавливаю Ollama...[/cyan]")

    try:
        if system == "darwin" or system == "linux":
            cmd = "curl -fsSL https://ollama.com/install.sh | sh"
            result = subprocess.run(cmd, shell=True, check=False, capture_output=True, text=True)
            if result.returncode == 0:
                console.print("[green]✓ Ollama установлен![/green]")
                return True
            else:
                console.print(f"[red]Установка завершилась с ошибкой:[/red]\n{result.stderr}")
                return False
        else:
            console.print("Автоустановка на Windows не поддерживается этим скриптом.")
            console.print("Пожалуйста, скачай с https://ollama.com")
            return False
    except Exception as e:
        console.print(f"[red]Ошибка при установке Ollama: {e}[/red]")
        return False
