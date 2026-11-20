"""User configuration: API token and defaults, stored as TOML in the platform config dir."""

from __future__ import annotations

import os
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from platformdirs import user_config_dir, user_downloads_dir

ENV_TOKEN = "YUMMY_APP_TOKEN"


def config_path() -> Path:
    return Path(user_config_dir("yummy-dl", appauthor=False)) / "config.toml"


@dataclass
class Config:
    token: str = ""
    output_dir: str = ""
    quality: int = 720
    workers: int = 8
    theme: str = ""  # "" = follow system, "dark", "light" (GUI only)

    @property
    def effective_token(self) -> str | None:
        return os.environ.get(ENV_TOKEN) or self.token or None

    @property
    def effective_output_dir(self) -> Path:
        return Path(self.output_dir) if self.output_dir else Path(user_downloads_dir()) / "yummy-dl"


def load() -> Config:
    path = config_path()
    if not path.exists():
        return Config()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in known})


def save(cfg: Config) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in asdict(cfg).items():
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        else:
            lines.append(f"{key} = {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
