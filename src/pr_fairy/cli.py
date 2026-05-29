"""
PR Fairy CLI (focused on powerful LLM integration for watch --auto)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

import typer
from git import Repo as GitRepo
from rich.console import Console
from rich.panel import Panel

from pr_fairy.core.config import load_config
from pr_fairy.core.fixer import ProposedFix
from pr_fairy.core.llm_fixer import LLMMicroFixer
from pr_fairy.core.wizard import run_install_wizard

console = Console()

app = typer.Typer(
    name="fairy",
    help="✨ PR Fairy — ночная фея, которая чинит твой репозиторий пока ты спишь",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command()
def install():
    """
    Interactive one-command setup wizard.

    This is the main entrypoint called by:
    curl -fsSL https://get.prfairy.dev | bash
    """
    exit_code = run_install_wizard()
    raise typer.Exit(exit_code)


@app.command()
def watch(
    auto: Annotated[bool, typer.Option("--auto", help="Автоматически создавать PR")] = False,
    max_repos: Annotated[int, typer.Option("--max-repos")] = 12,
    use_llm: Annotated[bool, typer.Option("--llm", help="Включить мощный LLM-режим поиска правок")] = False,
    path: Annotated[str | None, typer.Option("--path")] = None,
    force: Annotated[bool, typer.Option("--force", hidden=True)] = False,
) -> None:
    """Ищет мелкий техдолг. С --llm использует локальную модель для умных правок."""
    from pr_fairy.core.llm import get_llm

    cfg = load_config()
    use_auto = auto or cfg.auto_mode

    console.print(Panel.fit(
        f"[bold magenta]🧚 PR Fairy Watch[/bold magenta]\n\n"
        f"Режим: {'[bold green]AUTO[/bold green]' if use_auto else 'REVIEW'}\n"
        f"LLM: {'[bold cyan]ВКЛЮЧЁН[/bold cyan] — ищу умные правки через модель' if use_llm else 'выключен (только эвристики)'}",
        border_style="magenta",
    ))

    # === Single repo mode ===
    if path:
        target = Path(path).resolve()
        if not (target / ".git").exists():
            console.print("[red]Не git-репозиторий[/red]")
            raise typer.Exit(1)

        g = GitRepo(target)
        is_clean = not g.is_dirty(untracked_files=False) if not force else True

        repos = [{"path": target, "name": target.name, "is_clean": is_clean}]
        console.print(f"\n[bold]Сканирую только:[/bold] {target}\n")
    else:
        # Simplified multi-repo discovery (real scanner was more advanced)
        from pr_fairy.core.scanner import RepoScanner
        scanner = RepoScanner(cfg)
        result = scanner.find_repositories()
        repos = [{"path": r.path, "name": r.name, "is_clean": r.is_clean} for r in result.repos[:max_repos]]
        console.print(f"\n[bold]Найдено репозиториев:[/bold] {len(repos)}\n")

    total_fixes = 0
    llm_fixer = LLMMicroFixer() if use_llm else None

    for i, repo in enumerate(repos, 1):
        repo_path = repo["path"]
        console.print(f"[cyan]{i}.[/cyan] [bold]{repo['name']}[/bold]")

        if not repo["is_clean"] and not force:
            console.print("   [yellow]Пропуск (грязный репозиторий)[/yellow]")
            continue

        collected: list[ProposedFix] = []

        # 1. Static safe detectors (whitespace etc.)
        # (Simplified — in full version we call find_safe_fixes)

        # 2. LLM suggestions (the important part)
        if use_llm and llm_fixer:
            try:
                console.print("   [cyan]Запрашиваю умные правки у локальной модели...[/cyan]")
                llm_fixes = llm_fixer.find_llm_fixes(
                    repo_path,
                    max_files_to_ask=5,
                    max_suggestions=2,
                )
                for fix in llm_fixes:
                    console.print(f"   [magenta]LLM[/magenta] → {fix.description} (conf {fix.confidence:.0%})")
                    collected.append(fix)
                if not llm_fixes:
                    console.print("   [dim]Модель не нашла безопасных правок в этом репозитории[/dim]")
            except Exception as e:
                console.print(f"   [dim]LLM ошибка: {e}[/dim]")

        if collected:
            total_fixes += len(collected)
            console.print(f"   [green]Готово к правке: {len(collected)}[/green]")

            if use_auto:
                # Here we would call GitOps to create branch + apply + commit + PR
                console.print("   [bold green]В AUTO режиме — применила бы и открыла PR[/bold green]")
        else:
            console.print("   [dim]Ничего интересного не найдено[/dim]")

    if llm_fixer:
        llm_fixer.close()

    console.print(f"\n[bold]Всего предложено правок:[/bold] [green]{total_fixes}[/green]\n")


@app.command()
def fix(path: str = ".", apply: bool = False):
    """Быстрый просмотр правок (включая LLM при наличии флага в будущем)."""
    console.print("[yellow]Используй `fairy watch --path . --llm` для мощного анализа[/yellow]")


@app.command()
def llm_test(
    file: Annotated[str, typer.Argument(help="Путь к файлу для анализа моделью")],
    model: Annotated[str | None, typer.Option("--model", help="Принудительно использовать конкретную модель")] = None,
    no_auto: Annotated[bool, typer.Option("--no-auto", help="Отключить умный подбор модели (для чистой отладки промпта)")] = False,
):
    """
    Отладочная команда: напрямую спросить модель про один файл.

    Полезна для тестирования качества промпта и выбранной модели.
    """
    from pr_fairy.core.llm import get_llm

    target = Path(file).resolve()
    if not target.exists():
        console.print("[red]Файл не найден[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]Анализирую файл умной моделью...[/cyan] {target}\n")

    llm = get_llm(model, auto_select_for_llm=not no_auto)
    content = target.read_text(encoding="utf-8", errors="ignore")

    console.print(f"[dim]Используется модель:[/dim] {llm.model}\n")

    suggestion = llm.suggest_for_file(target, target.parent, content)

    if suggestion:
        console.print("[bold green]✓ Модель предложила правку[/bold green]")
        console.print(f"  Причина:     {suggestion.reason}")
        console.print(f"  Уверенность: {suggestion.confidence:.0%}")
        console.print("\n[bold]Unified diff:[/bold]")
        console.print(suggestion.diff)
    else:
        console.print("[yellow]Модель отказалась предлагать правки.[/yellow]")
        console.print("\n[dim]Возможные причины:[/dim]")
        console.print("  • В файле действительно нет очевидных безопасных улучшений")
        console.print("  • Модель очень консервативна (это по дизайну PR Fairy)")
        console.print("  • Попробуй --no-auto с уже скачанной хорошей моделью")

    llm.close()


if __name__ == "__main__":
    app()
