"""
Minimal repo scanner used by the CLI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pr_fairy.core.config import load_config


@dataclass
class DiscoveredRepo:
    path: Path
    name: str
    is_clean: bool = True


class RepoScanner:
    def __init__(self, config=None):
        self.config = config or load_config()

    def find_repositories(self):
        from pr_fairy.core.config import load_config
        cfg = load_config()

        repos = []
        for base in cfg.watch_paths:
            base_path = Path(base).expanduser()
            if not base_path.exists():
                continue
            for item in base_path.iterdir():
                if (item / ".git").exists():
                    repos.append(DiscoveredRepo(path=item, name=item.name))
        return type("Result", (), {"repos": repos})()
