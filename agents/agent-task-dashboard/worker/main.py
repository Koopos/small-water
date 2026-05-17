from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


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


def execute_code_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": f"Placeholder code worker completed {task.get('taskKey')}",
        "result": "not_implemented",
        "taskType": task.get("type"),
    }


def execute_image_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": f"Placeholder image worker completed {task.get('taskKey')}",
        "result": "not_implemented",
        "taskType": task.get("type"),
    }


def execute_content_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": f"Placeholder content worker completed {task.get('taskKey')}",
        "result": "not_implemented",
        "taskType": task.get("type"),
    }


EXECUTORS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "agent-dev": execute_code_task,
    "agent-image": execute_image_task,
    "agent-video-script": execute_content_task,
    "agent-article": execute_content_task,
    "agent-hot-content": execute_content_task,
    "agent-dating-post": execute_content_task,
    "agent-task": execute_content_task,
}


def run_once(config: WorkerConfig) -> bool:
    task = claim_task(config)
    if not task:
        return False

    task_id = str(task["id"])
    task_type = str(task.get("type", "agent-task"))
    executor = EXECUTORS.get(task_type)
    if executor is None:
        fail_task(config, task_id, f"Unsupported task type: {task_type}")
        return True

    try:
        payload = executor(task)
        complete_task(config, task_id, payload)
        return True
    except Exception as exc:  # noqa: BLE001
        fail_task(config, task_id, str(exc), {"taskType": task_type})
        return True


def parse_args(argv: list[str]) -> WorkerConfig:
    parser = argparse.ArgumentParser(description="Queue worker for agent-task-dashboard")
    parser.add_argument("--api-base-url", default=os.environ.get("API_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--worker-pool", default=os.environ.get("WORKER_POOL", "content"), choices=["code", "image", "content"])
    parser.add_argument("--worker-id", default=os.environ.get("WORKER_ID", f"worker-{os.getpid()}"))
    parser.add_argument("--poll-interval", type=int, default=int(os.environ.get("POLL_INTERVAL_SECONDS", "5")))
    args = parser.parse_args(argv)
    return WorkerConfig(
        api_base_url=args.api_base_url,
        worker_pool=args.worker_pool,
        worker_id=args.worker_id,
        poll_interval_seconds=args.poll_interval,
    )


def main(argv: list[str] | None = None) -> int:
    config = parse_args(argv or sys.argv[1:])
    print(f"Worker starting: pool={config.worker_pool} id={config.worker_id} api={config.api_base_url}")

    while True:
        did_work = run_once(config)
        if not did_work:
            time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
