from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CommandResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CommandSandbox:
    """Minimal command executor for L0/L1 modes."""

    def __init__(self, mode: str = "l0", timeout_seconds: int = 30, cwd: Optional[Path] = None) -> None:
        if mode not in {"l0", "l1"}:
            raise ValueError(f"Unsupported sandbox mode: {mode}")
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.cwd = cwd

    def run(self, command: str) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
            )

        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )
