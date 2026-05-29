from pathlib import Path
from pydantic import BaseModel, Field
import os

class FairyConfig(BaseModel):
    # Language for communication with the fairy (default English as per spec)
    language: str = "en"          # "en" or "ru" for now

    # Core model used by the fairy (especially for --llm smart fixes)
    model: str = "gemma4:e4b"

    watch_paths: list[str] = Field(default_factory=lambda: [str(Path.home() / "repos"), str(Path.home() / "projects")])
    github_token: str | None = None
    auto_mode: bool = True
    max_prs_per_night: int = 5
    ollama_host: str = "http://localhost:11434"

def load_config() -> FairyConfig:
    return FairyConfig()


def save_config(config: FairyConfig) -> None:
    # Minimal implementation for wizard (in real version this writes to ~/.config/pr-fairy/config.yaml)
    pass


def update_config(**kwargs) -> FairyConfig:
    cfg = load_config()
    for k, v in kwargs.items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    save_config(cfg)
    return cfg
