from __future__ import annotations

from pathlib import Path

from hermit.companion import appbundle


def test_install_app_bundle_creates_expected_structure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(appbundle, "_bundle_python_target", lambda: Path("/usr/local/bin/python3"))
    bundle = appbundle.install_app_bundle(
        target=tmp_path / "Hermit Menu.app",
        adapter="feishu",
        profile="codex-local",
        base_dir=tmp_path / ".hermit",
    )

    launcher = bundle / "Contents" / "MacOS" / "HermitMenu"
    info_plist = bundle / "Contents" / "Info.plist"

    assert launcher.exists()
    assert info_plist.exists()
    assert (bundle / "Contents" / "MacOS" / "python3").is_symlink()
    launcher_text = launcher.read_text(encoding="utf-8")
    assert 'export HERMIT_PROFILE="codex-local"' in launcher_text
    assert 'exec "$APP_ROOT/python3" -m hermit.companion.menubar --adapter "feishu"' in launcher_text
