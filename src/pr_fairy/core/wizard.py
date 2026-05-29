"""
Interactive setup wizard for PR Fairy (one-command experience).

New flow (as requested):
1. Welcome
2. Choose default language (EN by default)
3. Ollama check + install if needed
4. Smart model selection: download recommended OR pick from already installed
5. Optional tokens + watch folders
6. Success screen
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from pr_fairy.core.config import FairyConfig, load_config, save_config
from pr_fairy.core.model_recommender import (
    LLMModelRecommendation,
    get_llm_model_recommendations,
    print_llm_model_table,
)
from pr_fairy.core.ollama import (
    ensure_suitable_llm_model,
    get_installed_ollama_models,
    is_ollama_installed,
    start_ollama_if_needed,
)

console = Console()


LANGUAGES = {
    "en": "English",
    "ru": "Русский",
}

# Simple i18n for the wizard
# When user chooses language, all subsequent texts switch

TRANSLATIONS = {
    "en": {
        "welcome_title": "✨  PR FAIRY  ✨\nA night fairy who fixes your repository while you sleep",
        "welcome_question": "Shall we set you up in ~30 seconds?",
        "welcome_confirm": "Continue setup",

        "lang_prompt": "🌍 Choose default language for communication with PR Fairy",
        "lang_help": "The fairy will use this language for all messages and Pull Request descriptions.",
        "lang_question": "Default language:",
        "lang_set": "Default language set to",

        "ollama_installed": "Ollama is installed",
        "ollama_not_installed": "Ollama is not installed.",
        "ollama_install_question": "Install Ollama now?",
        "ollama_install_success": "Ollama installed successfully",
        "ollama_install_failed": "Failed to install Ollama",
        "ollama_required": "Ollama is required for PR Fairy to work.",

        "model_header": "🧠 Choose the model for smart fixes (--llm mode)",
        "model_installed_list": "Already installed models:",
        "model_download_recommended": "Download recommended model",
        "model_choose_installed": "Choose from already installed models",
        "model_skip": "Skip for now",
        "model_what_to_do": "What would you like to do?",
        "model_skipped": "Model setup skipped. You can configure it later with `fairy models` or `fairy watch --llm`.",
        "model_no_installed": "No models installed yet. Downloading the recommended one...",

        "final_title": "PR Fairy is ready!",
        "final_language": "Default language",
        "final_model": "Smart model",
        "final_watch": "Watching folders",
        "final_commands": "You can now run:",
        "final_magic": "First night magic starts now ✨",
        "final_start_now": "Start the fairy now? (fairy watch --llm)",
        "final_goodbye": "Thank you for trusting the fairy. Sweet dreams",
    },
    "ru": {
        "welcome_title": "✨  PR FAIRY  ✨\nНочная фея, которая чинит твой репозиторий пока ты спишь",
        "welcome_question": "Установим тебя за ~30 секунд?",
        "welcome_confirm": "Продолжить установку",

        "lang_prompt": "🌍 Выбери язык общения с PR Fairy по умолчанию",
        "lang_help": "Фея будет использовать этот язык во всех сообщениях и описаниях Pull Request.",
        "lang_question": "Язык по умолчанию:",
        "lang_set": "Язык по умолчанию установлен на",

        "ollama_installed": "Ollama уже установлен",
        "ollama_not_installed": "Ollama не установлен.",
        "ollama_install_question": "Установить Ollama сейчас?",
        "ollama_install_success": "Ollama успешно установлен",
        "ollama_install_failed": "Не удалось установить Ollama",
        "ollama_required": "Ollama необходим для работы PR Fairy.",

        "model_header": "🧠 Выбери модель для умного режима (--llm)",
        "model_installed_list": "Уже установленные модели:",
        "model_download_recommended": "Скачать рекомендованную модель",
        "model_choose_installed": "Выбрать из уже установленных моделей",
        "model_skip": "Пропустить сейчас",
        "model_what_to_do": "Что хочешь сделать?",
        "model_skipped": "Настройка модели пропущена. Позже можно настроить через `fairy models` или `fairy watch --llm`.",
        "model_no_installed": "Пока нет установленных моделей. Скачиваю рекомендованную...",

        "final_title": "PR Fairy готова!",
        "final_language": "Язык по умолчанию",
        "final_model": "Умная модель",
        "final_watch": "Наблюдаемые папки",
        "final_commands": "Теперь можешь запускать:",
        "final_magic": "Первая ночь — фея уже в деле ✨",
        "final_start_now": "Запустить фею прямо сейчас? (fairy watch --llm)",
        "final_goodbye": "Спасибо, что доверился фее. Спокойной ночи",
    }
}

_current_lang = "en"


def t(key: str, lang: str | None = None) -> str:
    """Get translated string for the given key."""
    lang = lang or _current_lang
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def show_welcome() -> bool:
    _clear()
    title = t("welcome_title")
    console.print(Panel(title, style="bold magenta", border_style="bright_magenta"))
    console.print(f"\n[bold]{t('welcome_question')}[/bold]")

    # If stdin is not a TTY (e.g. running in a script or piped install),
    # we cannot do interactive prompts. Exit gracefully instead of ugly "Aborted."
    if not sys.stdin.isatty():
        console.print("\n[yellow]Non-interactive environment detected.[/yellow]")
        console.print("Please run [bold]fairy install[/bold] manually in your terminal to complete setup.")
        return False

    return Confirm.ask(t("welcome_confirm"), default=True)


def choose_language() -> str:
    """Step 2: Language selection (default EN). After selection, the rest of the wizard switches language."""
    global _current_lang

    _clear()
    console.print("[bold]🌍 Choose default language / Выбери язык по умолчанию[/bold]\n")
    console.print(
        "The fairy will speak this language in all messages and Pull Requests.\n"
        "Фея будет использовать этот язык во всех сообщениях и описаниях PR.\n"
    )

    choices = [
        "en — English (recommended)",
        "ru — Русский"
    ]
    default = choices[0]

    answer = questionary.select(
        "Default language / Язык по умолчанию:",
        choices=choices,
        default=default,
    ).ask()

    if not answer:
        _current_lang = "en"
        return "en"

    if answer.startswith("ru"):
        _current_lang = "ru"
        console.print("\n[green]✓[/green] Язык по умолчанию: [bold]Русский[/bold]\n")
    else:
        _current_lang = "en"
        console.print("\n[green]✓[/green] Default language set to: [bold]English[/bold]\n")

    return _current_lang


def install_ollama_if_needed() -> bool:
    lang = _current_lang

    if is_ollama_installed():
        console.print(f"[green]✓[/green] {t('ollama_installed', lang)}")
        start_ollama_if_needed()
        return True

    console.print(f"\n[yellow]{t('ollama_not_installed', lang)}[/yellow]")
    cmd = "curl -fsSL https://ollama.com/install.sh | sh"

    if Confirm.ask(f"{t('ollama_install_question', lang)} ({cmd})", default=True):
        import subprocess
        try:
            subprocess.run(cmd, shell=True, check=True)
            console.print(f"[green]✓[/green] {t('ollama_install_success', lang)}")
            start_ollama_if_needed()
            return True
        except Exception as e:
            console.print(f"[red]{t('ollama_install_failed', lang)}: {e}[/red]")
            return False

    console.print(f"[yellow]{t('ollama_required', lang)}[/yellow]")
    return False


def choose_llm_model_flow(cfg: FairyConfig) -> str:
    """Model selection step (respects chosen language)"""
    lang = _current_lang

    console.print(f"\n[bold]{t('model_header', lang)}[/bold]\n")

    installed = get_installed_ollama_models()

    if installed:
        console.print(f"[dim]{t('model_installed_list', lang)}[/dim]")
        for m in installed[:6]:
            console.print(f"  • {m}")
        console.print()

    # Show recommendations (table headers stay in English for technical accuracy)
    print_llm_model_table("Recommended models for intelligent micro-fixes")

    best = get_llm_model_recommendations()[0]

    choices = [
        f"⭐ {t('model_download_recommended', lang)}: {best.tag} (~{best.size_gb:.1f} GB)",
        t('model_choose_installed', lang),
        t('model_skip', lang),
    ]

    answer = questionary.select(
        t('model_what_to_do', lang),
        choices=choices,
        default=choices[0],
    ).ask()

    if not answer or t('model_skip', lang) in answer:
        console.print(f"[yellow]{t('model_skipped', lang)}[/yellow]")
        return cfg.model or best.tag

    if t('model_download_recommended', lang) in answer:
        chosen = ensure_suitable_llm_model(best.tag, interactive=True)
        cfg.model = chosen
        return chosen

    # Pick from installed
    if not installed:
        console.print(f"[yellow]{t('model_no_installed', lang)}[/yellow]")
        chosen = ensure_suitable_llm_model(best.tag, interactive=True)
        cfg.model = chosen
        return chosen

    model_choice = questionary.select(
        t('model_choose_installed', lang),
        choices=installed,
    ).ask()

    cfg.model = model_choice or best.tag
    return cfg.model


def final_summary(cfg: FairyConfig):
    _clear()
    lang = _current_lang
    lang_name = LANGUAGES.get(cfg.language, cfg.language)

    msg = f"""
✅ [bold green]{t('final_title', lang)}[/bold green]

🌍 {t('final_language', lang)}: [bold]{lang_name}[/bold]
🧠 {t('final_model', lang)}: [bold]{cfg.model}[/bold]
🚀 {t('final_watch', lang)}: {', '.join(cfg.watch_paths)}

{t('final_commands', lang)}
  [cyan]fairy watch --llm[/cyan]
  [cyan]fairy watch --auto[/cyan]

{t('final_magic', lang)}
"""

    console.print(Panel(msg.strip(), border_style="green", padding=(1, 2)))


def run_install_wizard() -> int:
    if not show_welcome():
        console.print(t("final_goodbye") + " 👋")
        return 0

    # === NEW FLOW ===
    # 1. Language selection (default EN)
    lang = choose_language()

    # 2. Ollama
    if not install_ollama_if_needed():
        return 1

    # 3. Model selection (download recommended OR pick installed)
    cfg = load_config()
    cfg.language = lang
    chosen_model = choose_llm_model_flow(cfg)
    cfg.model = chosen_model

    # 4. Save early
    save_config(cfg)

    # 5. Optional future steps (can be expanded later)
    console.print(f"\n[dim]{t('model_skipped', _current_lang)}[/dim]")

    # 6. Beautiful finish
    final_summary(cfg)

    if Confirm.ask(f"\n{t('final_start_now')}", default=True):
        console.print(f"\n[bold cyan]{t('final_start_now')}[/bold cyan]")

    console.print(f"\n[dim]{t('final_goodbye')} 💤[/dim]\n")
    return 0
