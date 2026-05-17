from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from .common import WorkerConfig, claim_task, complete_task, fail_task, fetch_task
from .content import build_content_task_output
from .code import build_code_output
from .image import build_image_output

def run_once(config: WorkerConfig) -> bool:
    task_claim = claim_task(config)
    if not task_claim:
        return False

    task_id = str(task_claim["id"])
    task = fetch_task(config, task_id)
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


EXECUTORS = {
    "agent-dev": build_code_output,
    "agent-image": build_image_output,
    "agent-video-script": build_content_task_output,
    "agent-article": build_content_task_output,
    "agent-hot-content": build_content_task_output,
    "agent-dating-post": build_content_task_output,
    "agent-task": build_content_task_output,
}
