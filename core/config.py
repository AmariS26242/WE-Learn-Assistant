"""配置加载与默认配置管理。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class WebConfig:
    browser: str = "msedge"
    headless: bool = False
    timeout_ms: int = 15000
    cdp_endpoint: str = ""
    target_url: str = "https://welearn.sflep.com/"


@dataclass(slots=True)
class AndroidConfig:
    adb_path: str = "adb"
    command_timeout_sec: int = 10
    screenshot_remote_path: str = "/sdcard/we_learn_screen.png"
    ui_dump_remote_path: str = "/sdcard/we_learn_ui.xml"


@dataclass(slots=True)
class SafetyConfig:
    mask_logs: bool = True
    allow_credential_autofill: bool = False


@dataclass(slots=True)
class AppConfig:
    name: str = "WE-Learn-Assistant"
    log_level: str = "INFO"
    data_dir: str = "data"
    screenshot_dir: str = "screenshots"
    db_path: str = "data/we_learn_assistant.db"
    web: WebConfig = field(default_factory=WebConfig)
    android: AndroidConfig = field(default_factory=AndroidConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


def _merge_dict(raw: dict[str, Any]) -> AppConfig:
    app_raw = raw.get("app", {}) or {}
    db_raw = raw.get("database", {}) or {}
    web_raw = raw.get("web", {}) or {}
    android_raw = raw.get("android", {}) or {}
    safety_raw = raw.get("safety", {}) or {}

    return AppConfig(
        name=str(app_raw.get("name", "WE-Learn-Assistant")),
        log_level=str(app_raw.get("log_level", "INFO")),
        data_dir=str(app_raw.get("data_dir", "data")),
        screenshot_dir=str(app_raw.get("screenshot_dir", "screenshots")),
        db_path=str(db_raw.get("path", "data/we_learn_assistant.db")),
        web=WebConfig(
            browser=str(web_raw.get("browser", "msedge")),
            headless=bool(web_raw.get("headless", False)),
            timeout_ms=int(web_raw.get("timeout_ms", 15000)),
            cdp_endpoint=str(web_raw.get("cdp_endpoint", "")),
            target_url=str(web_raw.get("target_url", "https://welearn.sflep.com/")),
        ),
        android=AndroidConfig(
            adb_path=str(android_raw.get("adb_path", "adb")),
            command_timeout_sec=int(android_raw.get("command_timeout_sec", 10)),
            screenshot_remote_path=str(
                android_raw.get("screenshot_remote_path", "/sdcard/we_learn_screen.png")
            ),
            ui_dump_remote_path=str(
                android_raw.get("ui_dump_remote_path", "/sdcard/we_learn_ui.xml")
            ),
        ),
        safety=SafetyConfig(
            mask_logs=bool(safety_raw.get("mask_logs", True)),
            # 安全红线：强制禁止凭证自动填充
            allow_credential_autofill=False,
        ),
    )


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """按优先级加载配置文件（本地 config.yaml -> 示例配置 -> 默认配置）。"""
    candidates: list[Path] = []
    if config_path is not None:
        candidates.append(Path(config_path))
    else:
        candidates.extend(
            [
                Path("config/config.yaml"),
                Path("config/config.example.yaml"),
            ]
        )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            with candidate.open("r", encoding="utf-8") as fh:
                loaded = yaml.safe_load(fh) or {}
            if isinstance(loaded, dict):
                return _merge_dict(loaded)

    return AppConfig()
