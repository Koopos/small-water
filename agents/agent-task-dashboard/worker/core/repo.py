from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .common import WorkerError, safe_text
from .fs import resolve_artifact_root

def worker_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]

def github_clone_url(value: Any) -> str | None:
    text = safe_text(value)
    if not text:
        return None
    if "github.com/" in text:
        suffix = text.split("github.com/", 1)[1].strip("/")
        suffix = suffix.removesuffix(".git")
        parts = suffix.split("/")
        if len(parts) >= 2:
            return f"https://github.com/{parts[0]}/{parts[1]}.git"
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:")
    match = re.match(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$", text)
    if match:
        return f"https://github.com/{match.group('owner')}/{match.group('repo')}.git"
    return None

def is_transient_git_clone_error(message: str) -> bool:
    text = message.lower()
    patterns = [
        "gnutls recv error",
        "tls connection was non-properly terminated",
        "rpc failed",
        "curl 56",
        "ssl connection timeout",
        "connection reset by peer",
        "http2 stream",
        "the remote end hung up unexpectedly",
    ]
    return any(pattern in text for pattern in patterns)

def clone_github_repo(clone_url: str, checkout_dir: Path) -> Path:
    if checkout_dir.exists() and (checkout_dir / ".git").exists():
        return checkout_dir
    checkout_dir.parent.mkdir(parents=True, exist_ok=True)

    from worker import main as worker_main

    env = os.environ.copy()
    env.setdefault("GIT_HTTP_VERSION", "HTTP/1.1")
    env.setdefault("GIT_TERMINAL_PROMPT", "0")

    command = ["git", "clone", "--depth", "1", "--single-branch", clone_url, str(checkout_dir)]
    last_error = ""
    attempts = 3
    for attempt in range(1, attempts + 1):
        result = worker_main.run_external_command(command, cwd=checkout_dir.parent, env=env, stdin_text="")
        if result.returncode == 0:
            return checkout_dir
        last_error = (result.stderr or result.stdout or f"git clone failed: {clone_url}").strip()
        if attempt < attempts and is_transient_git_clone_error(last_error):
            time.sleep(2 ** (attempt - 1))
            continue
        break

    raise WorkerError(last_error or f"git clone failed: {clone_url}")

def resolve_repo_path(task: dict[str, Any], task_input_data: dict[str, Any], project: dict[str, Any]) -> tuple[str, str | None]:
    local_path = safe_text(project.get("localPath"), "")
    if local_path and Path(local_path).exists():
        return local_path, None

    candidates: list[Any] = []
    references = task_input_data.get("references") if isinstance(task_input_data.get("references"), list) else []
    candidates.extend(references)
    candidates.append(project.get("repo"))
    candidates.append(project.get("localPath"))

    from worker import main as worker_main

    for candidate in candidates:
        clone_url = github_clone_url(candidate)
        if not clone_url:
            continue
        task_id = safe_text(task.get("id"), "task")
        checkout_dir = worker_main.worker_repo_root() / ".run" / "code-repos" / task_id
        worker_main.clone_github_repo(clone_url, checkout_dir)
        return str(checkout_dir), clone_url

    return "", None
