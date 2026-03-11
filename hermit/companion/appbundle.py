from __future__ import annotations

import argparse
import plistlib
import os
import subprocess
import sys
from pathlib import Path

from hermit.companion.control import hermit_base_dir

APP_NAME = "Hermit Menu"
BUNDLE_ID = "com.hermit.menubar"


def app_path(target: Path | None = None) -> Path:
    return (target or (Path.home() / "Applications" / f"{APP_NAME}.app")).expanduser()


def _launcher_command() -> list[str]:
    companion_bin = Path(sys.executable).parent / "hermit-menubar"
    if companion_bin.exists():
        return [str(companion_bin)]
    return [sys.executable, "-m", "hermit.companion.menubar"]


def _bundle_python_target() -> Path:
    return Path(sys.executable).resolve()


def install_app_bundle(
    *,
    target: Path | None = None,
    adapter: str = "feishu",
    profile: str | None = None,
    base_dir: Path | None = None,
) -> Path:
    bundle = app_path(target)
    contents = bundle / "Contents"
    macos_dir = contents / "MacOS"
    resources_dir = contents / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    info = {
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": "HermitMenu",
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSUIElement": True,
    }
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))

    resolved_base_dir = (base_dir or hermit_base_dir()).expanduser()
    env_lines = [f'export HERMIT_BASE_DIR="{resolved_base_dir}"']
    if profile:
        env_lines.append(f'export HERMIT_PROFILE="{profile}"')
    bundled_python = macos_dir / "python3"
    target_python = _bundle_python_target()
    if bundled_python.exists() or bundled_python.is_symlink():
        bundled_python.unlink()
    os.symlink(target_python, bundled_python)
    launcher = "\n".join(
        [
            "#!/bin/zsh",
            "set -e",
            'APP_ROOT="$(cd "$(dirname "$0")" && pwd)"',
            *env_lines,
            'exec "$APP_ROOT/python3" -m hermit.companion.menubar '
            f'--adapter "{adapter}"',
            "",
        ]
    )
    launcher_path = macos_dir / "HermitMenu"
    launcher_path.write_text(launcher, encoding="utf-8")
    launcher_path.chmod(0o755)
    return bundle


def open_app_bundle(target: Path | None = None) -> None:
    subprocess.Popen(["open", str(app_path(target))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def login_item_enabled(name: str = APP_NAME) -> bool:
    script = (
        'tell application "System Events"\n'
        f'  return exists login item "{name}"\n'
        "end tell"
    )
    try:
        output = _run_osascript(script).lower()
    except Exception:
        return False
    return output == "true"


def enable_login_item(target: Path | None = None) -> str:
    bundle = app_path(target)
    if not bundle.exists():
        raise RuntimeError(f"App bundle not found: {bundle}")
    script = (
        'tell application "System Events"\n'
        f'  if exists login item "{APP_NAME}" then delete login item "{APP_NAME}"\n'
        f'  make login item at end with properties {{name:"{APP_NAME}", path:"{bundle}", hidden:false}}\n'
        "end tell"
    )
    _run_osascript(script)
    return f"Enabled login item for {APP_NAME}."


def disable_login_item(name: str = APP_NAME) -> str:
    script = (
        'tell application "System Events"\n'
        f'  if exists login item "{name}" then delete login item "{name}"\n'
        "end tell"
    )
    _run_osascript(script)
    return f"Disabled login item for {name}."


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Hermit menu bar app bundle")
    parser.add_argument("--target", default=None, help="Custom .app target path.")
    parser.add_argument("--adapter", default="feishu", help="Adapter to manage.")
    parser.add_argument("--profile", default=None, help="Optional HERMIT_PROFILE override.")
    parser.add_argument("--base-dir", default=None, help="Optional HERMIT_BASE_DIR override.")
    parser.add_argument("--open", action="store_true", help="Open the installed app.")
    parser.add_argument("--enable-login-item", action="store_true", help="Enable companion login item.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.platform != "darwin":
        print("Hermit menu bar app bundle is only supported on macOS.", file=sys.stderr)
        return 1
    args = _parse_args(argv or sys.argv[1:])
    target = Path(args.target).expanduser() if args.target else None
    base_dir = Path(args.base_dir).expanduser() if args.base_dir else None
    bundle = install_app_bundle(target=target, adapter=args.adapter, profile=args.profile, base_dir=base_dir)
    print(f"Installed app bundle: {bundle}")
    if args.enable_login_item:
        print(enable_login_item(bundle))
    if args.open:
        open_app_bundle(bundle)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
