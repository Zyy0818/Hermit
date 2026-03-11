from __future__ import annotations

from pathlib import Path

from hermit.config import Settings
from hermit.i18n import normalize_locale, tr
from hermit.plugin.loader import parse_manifest


def test_normalize_locale_aliases() -> None:
    assert normalize_locale("zh_CN.UTF-8".split(".", 1)[0]) == "zh-CN"
    assert normalize_locale("en") == "en-US"


def test_settings_normalizes_locale(monkeypatch) -> None:
    monkeypatch.setenv("HERMIT_LOCALE", "zh")

    settings = Settings()

    assert settings.locale == "zh-CN"


def test_translate_uses_locale_catalog() -> None:
    assert tr("cli.app.help", locale="zh-CN") == "Hermit 个人 AI Agent CLI。"
    assert tr("cli.app.help", locale="en-US") == "Hermit personal AI agent CLI."


def test_translate_falls_back_to_default_text() -> None:
    assert tr("missing.key", locale="zh-CN", default="fallback") == "fallback"


def test_parse_manifest_uses_description_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMIT_LOCALE", "zh-CN")
    plugin_dir = tmp_path / "usage"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.toml").write_text(
        """
[plugin]
name = "usage"
description_key = "plugin.usage.description"
description = "Show token usage statistics for the current session"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    manifest = parse_manifest(plugin_dir)

    assert manifest is not None
    assert manifest.description == "显示当前会话的 token 消耗统计"
