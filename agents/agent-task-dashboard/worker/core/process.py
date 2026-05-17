from __future__ import annotations

import subprocess
from typing import Any


def run_external_command(command: str | list[str], *, cwd: str | None, env: dict[str, str], stdin_text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=stdin_text,
        capture_output=True,
        text=True,
        shell=isinstance(command, str),
        check=False,
    )
