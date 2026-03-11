from __future__ import annotations

from pathlib import Path

from hermit.companion import control


def test_read_pid_rejects_invalid_content(tmp_path: Path) -> None:
    path = tmp_path / "serve.pid"
    path.write_text("abc", encoding="utf-8")

    assert control.read_pid(path) is None


def test_service_status_reports_pid_without_autostart(tmp_path: Path, monkeypatch) -> None:
    base_dir = tmp_path / ".hermit"
    base_dir.mkdir()
    pid_file = base_dir / "serve-feishu.pid"
    pid_file.write_text("123", encoding="utf-8")
    monkeypatch.setattr(control, "process_exists", lambda pid: pid == 123)
    monkeypatch.setattr(control.sys, "platform", "linux")

    status = control.service_status("feishu", base_dir=base_dir)

    assert status.pid_file == pid_file
    assert status.pid == 123
    assert status.running is True
    assert status.autostart_installed is False
    assert status.autostart_loaded is False


def test_ensure_config_file_writes_template(tmp_path: Path) -> None:
    path = control.ensure_config_file(tmp_path / ".hermit")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert 'default_profile = "default"' in text
    assert "[profiles.default]" in text
