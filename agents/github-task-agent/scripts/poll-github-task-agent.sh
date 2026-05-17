#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./poll-github-task-agent.sh owner/repo path/to/tasks.json [max_tasks]
#
# This script is now a scheduler, not a "spawn 3 identical agents" loop.
# It claims tasks once, limits concurrency by worker pool, and then
# dispatches one worker per claimed task.

if [ $# -lt 2 ]; then
  echo "Usage: $0 owner/repo path/to/tasks.json [max_tasks]"
  exit 1
fi

REPO="$1"
TASK_FILE="$2"
MAX_TASKS="${3:-0}"
WORKROOT="${GITHUB_AGENT_WORKROOT:-$HOME/AIGC/agents/github-task-agent/repos}"
REPO_DIR="$WORKROOT/${REPO//\//__}"
PROMPT_FILE="$HOME/AIGC/agents/github-task-agent/prompts/polling-agent.md"
LOCK_DIR="$WORKROOT/.locks"
LOCK_FILE="$LOCK_DIR/${REPO//\//__}.scheduler.lock"
LOGDIR="$HOME/AIGC/agents/github-task-agent/logs"
CLAIM_SCRIPT="$HOME/AIGC/agents/github-task-agent/scripts/dispatch-task-worker.sh"

mkdir -p "$WORKROOT" "$LOCK_DIR" "$LOGDIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "Scheduler already running for $REPO — exiting."
  exit 0
fi

if [ ! -d "$REPO_DIR/.git" ]; then
  gh repo clone "$REPO" "$REPO_DIR"
fi

cd "$REPO_DIR"

DEFAULT_BRANCH=$(gh repo view "$REPO" --json defaultBranchRef -q '.defaultBranchRef.name')

sync_repo() {
  git fetch origin --prune
  git checkout "$DEFAULT_BRANCH"
  git pull --ff-only origin "$DEFAULT_BRANCH"
}

sync_repo

if [ ! -f "$TASK_FILE" ]; then
  echo "Task file not found: $TASK_FILE"
  exit 0
fi

HOSTNAME="${HOSTNAME:-$(hostname)}"
SCHEDULER_NAME="${GITHUB_AGENT_NAME:-$HOSTNAME}"

# Worker pool limits: one scheduler can dispatch multiple tasks, but each pool is capped.
CODE_WORKERS="${GITHUB_AGENT_CODE_WORKERS:-1}"
IMAGE_WORKERS="${GITHUB_AGENT_IMAGE_WORKERS:-2}"
CONTENT_WORKERS="${GITHUB_AGENT_CONTENT_WORKERS:-2}"
LOCK_TTL_SECONDS="${GITHUB_AGENT_LOCK_TTL_SECONDS:-600}"

CLAIMED=$(
  python3 - "$TASK_FILE" "$SCHEDULER_NAME" "$LOCK_TTL_SECONDS" "$CODE_WORKERS" "$IMAGE_WORKERS" "$CONTENT_WORKERS" "$MAX_TASKS" <<'PY'
import datetime as dt
import json
import os
import sys
from collections import defaultdict


task_file, scheduler_name, lock_ttl_seconds, code_workers, image_workers, content_workers, max_tasks = sys.argv[1:8]
lock_ttl_seconds = int(lock_ttl_seconds)
code_workers = int(code_workers)
image_workers = int(image_workers)
content_workers = int(content_workers)
max_tasks = int(max_tasks)

POOL_MAP = {
    "agent-dev": "code",
    "agent-image": "image",
    "agent-video-script": "content",
    "agent-article": "content",
    "agent-hot-content": "content",
    "agent-dating-post": "content",
}
POOL_LIMITS = {
    "code": code_workers,
    "image": image_workers,
    "content": content_workers,
}
PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}
now = dt.datetime.now(dt.timezone.utc)
now_iso = now.isoformat().replace("+00:00", "Z")

with open(task_file, "r", encoding="utf-8") as fh:
    data = json.load(fh)

tasks = data.get("tasks", [])

# Reclaim stale locks before scheduling new work.
for task in tasks:
    if task.get("status") != "running":
        continue
    locked_at = task.get("locked_at")
    if not locked_at:
        continue
    try:
        locked_dt = dt.datetime.fromisoformat(str(locked_at).replace("Z", "+00:00"))
    except ValueError:
        continue
    if (now - locked_dt).total_seconds() > lock_ttl_seconds:
        task["status"] = "pending"
        task["locked_by"] = None
        task["locked_at"] = None
        task["started_at"] = None
        task["updated_at"] = now_iso
        task["error"] = task.get("error") or "Scheduler reclaimed stale lock"

pending = []
for index, task in enumerate(tasks):
    if task.get("status") != "pending":
        continue
    pool = POOL_MAP.get(task.get("type", ""))
    if not pool:
        continue
    created_at = task.get("created_at") or task.get("createdAt") or now_iso
    pending.append((
        PRIORITY_ORDER.get(str(task.get("priority", "normal")), 1),
        str(created_at),
        index,
        pool,
        task,
    ))

pending.sort(key=lambda item: (item[0], item[1], item[2]))

selected = []
pool_counts = defaultdict(int)

for _, _, _, pool, task in pending:
    if POOL_LIMITS.get(pool, 0) <= pool_counts[pool]:
        continue
    if max_tasks > 0 and len(selected) >= max_tasks:
        break

    task["status"] = "running"
    task["locked_by"] = scheduler_name
    task["locked_at"] = now_iso
    task["started_at"] = task.get("started_at") or now_iso
    task["updated_at"] = now_iso
    selected.append({"id": str(task.get("id", "")), "pool": pool})
    pool_counts[pool] += 1

if not selected:
    print("")
    sys.exit(0)

data["updated_at"] = now_iso
with open(task_file, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")

# Print claims as tab-separated lines for the shell scheduler.
for item in selected:
    print(f"{item['id']}\t{item['pool']}")
PY
)

if [ -z "$CLAIMED" ]; then
  echo "No pending tasks — exiting."
  exit 0
fi

echo "Claimed tasks:"
printf '%s\n' "$CLAIMED" | while IFS=$'\t' read -r TASK_ID TASK_POOL; do
  [ -z "${TASK_ID:-}" ] && continue
  echo "- $TASK_ID ($TASK_POOL)"
done

git add "$TASK_FILE"
CLAIM_COUNT=$(printf '%s\n' "$CLAIMED" | sed '/^$/d' | wc -l | tr -d ' ')
git commit -m "chore(agent): dispatch ${CLAIM_COUNT} task(s)"

echo "Pushing scheduler update..."
if ! git push origin "$DEFAULT_BRANCH"; then
  echo "Push conflict detected, aborting dispatch. Re-run the scheduler after syncing."
  git reset --hard "origin/$DEFAULT_BRANCH"
  exit 1
fi

printf '%s\n' "$CLAIMED" | while IFS=$'\t' read -r TASK_ID TASK_POOL; do
  [ -z "${TASK_ID:-}" ] && continue
  "$CLAIM_SCRIPT" "$REPO" "$TASK_FILE" "$TASK_ID" "$TASK_POOL" "$DEFAULT_BRANCH"
done

echo "Scheduler finished — workers dispatched."
