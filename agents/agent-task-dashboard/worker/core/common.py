from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class WorkerConfig:
    api_base_url: str
    worker_pool: str
    worker_id: str
    poll_interval_seconds: int = 5

class WorkerError(RuntimeError):
    pass

def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise WorkerError(f"HTTP {exc.code}: {body}") from exc

def claim_task(config: WorkerConfig) -> dict[str, Any] | None:
    response = http_json(
        "POST",
        f"{config.api_base_url.rstrip('/')}/api/worker-pools/{config.worker_pool}/claim",
        {"workerId": config.worker_id},
    )
    task = response.get("task")
    if not task:
        return None
    return task

def fetch_task(config: WorkerConfig, task_id: str) -> dict[str, Any]:
    response = http_json("GET", f"{config.api_base_url.rstrip('/')}/api/tasks/{task_id}")
    task = response.get("task")
    if not task:
        raise WorkerError(f"Task not found: {task_id}")
    return task

def complete_task(config: WorkerConfig, task_id: str, payload: dict[str, Any]) -> None:
    http_json(
        "POST",
        f"{config.api_base_url.rstrip('/')}/api/tasks/{task_id}/complete",
        {"workerId": config.worker_id, "payload": payload},
    )

def fail_task(config: WorkerConfig, task_id: str, error: str, payload: dict[str, Any] | None = None) -> None:
    http_json(
        "POST",
        f"{config.api_base_url.rstrip('/')}/api/tasks/{task_id}/fail",
        {"workerId": config.worker_id, "error": error, "payload": payload or {}},
    )

def parse_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return default
    return default

def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def task_input(task: dict[str, Any]) -> dict[str, Any]:
    return parse_json(task.get("inputJson") or task.get("input"), {}) or {}

def task_output(task: dict[str, Any]) -> dict[str, Any]:
    return parse_json(task.get("outputJson") or task.get("output"), {}) or {}

def task_artifacts(task: dict[str, Any]) -> list[Any]:
    artifacts = parse_json(task.get("artifactsJson") or task.get("artifacts"), [])
    return artifacts if isinstance(artifacts, list) else []

def safe_text(value: Any, fallback: str = "") -> str:
    text = str(value if value is not None else fallback).strip()
    return text or fallback
