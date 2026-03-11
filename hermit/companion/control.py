from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ServiceStatus:
    adapter: str
    pid_file: Path
    pid: int | None
    running: bool
    autostart_installed: bool
    autostart_loaded: bool


def hermit_base_dir() -> Path:
    raw = os.environ.get("HERMIT_BASE_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermit"


def hermit_log_dir(base_dir: Path | None = None) -> Path:
    root = base_dir or hermit_base_dir()
    return root / "logs"


def config_path(base_dir: Path | None = None) -> Path:
    root = base_dir or hermit_base_dir()
    return root / "config.toml"


def ensure_base_dir(base_dir: Path | None = None) -> Path:
    root = base_dir or hermit_base_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_config_file(base_dir: Path | None = None) -> Path:
    root = ensure_base_dir(base_dir)
    path = config_path(root)
    if not path.exists():
        path.write_text(
            "\n".join(
                [
                    '# Hermit profile catalog',
                    'default_profile = "default"',
                    "",
                    "[profiles.default]",
                    'provider = "claude"',
                    'model = "claude-3-7-sonnet-latest"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return path


def pid_path(adapter: str, base_dir: Path | None = None) -> Path:
    root = base_dir or hermit_base_dir()
    return root / f"serve-{adapter}.pid"


def read_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def process_exists(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def command_prefix() -> list[str]:
    hermit_bin = Path(sys.executable).parent / "hermit"
    if hermit_bin.exists():
        return [str(hermit_bin)]
    installed = shutil.which("hermit")
    if installed:
        return [installed]
    return [sys.executable, "-m", "hermit.main"]


def run_hermit_command(
    args: list[str],
    *,
    base_dir: Path | None = None,
    profile: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if base_dir is not None:
        env["HERMIT_BASE_DIR"] = str(base_dir)
    if profile:
        env["HERMIT_PROFILE"] = profile
    return subprocess.run(
        [*command_prefix(), *args],
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def service_status(adapter: str, *, base_dir: Path | None = None) -> ServiceStatus:
    from hermit import autostart as hermit_autostart

    resolved_base_dir = base_dir or hermit_base_dir()
    current_pid_path = pid_path(adapter, resolved_base_dir)
    pid = read_pid(current_pid_path)
    autostart_installed = False
    autostart_loaded = False
    if sys.platform == "darwin":
        plist_path = hermit_autostart._plist_path(adapter)
        autostart_installed = plist_path.exists()
        if autostart_installed:
            autostart_loaded = hermit_autostart._is_loaded(adapter)
    return ServiceStatus(
        adapter=adapter,
        pid_file=current_pid_path,
        pid=pid,
        running=process_exists(pid),
        autostart_installed=autostart_installed,
        autostart_loaded=autostart_loaded,
    )


def start_service(
    adapter: str,
    *,
    base_dir: Path | None = None,
    profile: str | None = None,
) -> str:
    resolved_base_dir = base_dir or hermit_base_dir()
    status = service_status(adapter, base_dir=resolved_base_dir)
    if status.running:
        return f"Hermit service is already running for '{adapter}' (PID {status.pid})."

    log_dir = hermit_log_dir(resolved_base_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"{adapter}-menubar-stdout.log"
    stderr_path = log_dir / f"{adapter}-menubar-stderr.log"
    env = os.environ.copy()
    env["HERMIT_BASE_DIR"] = str(resolved_base_dir)
    if profile:
        env["HERMIT_PROFILE"] = profile

    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        subprocess.Popen(
            [*command_prefix(), "serve", "--adapter", adapter],
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
    return f"Started Hermit service for '{adapter}'. Logs: {log_dir}"


def stop_service(adapter: str, *, base_dir: Path | None = None) -> str:
    current_status = service_status(adapter, base_dir=base_dir)
    if not current_status.running or current_status.pid is None:
        return f"Hermit service is not running for '{adapter}'."
    os.kill(current_status.pid, signal.SIGTERM)
    return f"Sent SIGTERM to Hermit service for '{adapter}' (PID {current_status.pid})."


def reload_service(adapter: str, *, base_dir: Path | None = None, profile: str | None = None) -> str:
    run_hermit_command(["reload", "--adapter", adapter], base_dir=base_dir, profile=profile)
    return f"Reload signal sent for '{adapter}'."


def open_path(path: Path) -> None:
    if sys.platform == "darwin":
        target = path if path.exists() else path.parent
        subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    raise RuntimeError("Opening paths is only implemented for macOS.")


def open_in_textedit(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(
            ["open", "-a", "TextEdit", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    raise RuntimeError("Opening TextEdit is only implemented for macOS.")
