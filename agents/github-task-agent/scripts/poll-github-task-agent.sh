#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./poll-github-task-agent.sh owner/repo .agent/tasks.json [max_tasks]
#
# Processes up to max_tasks (default 1) pending tasks.
# For horizontal scaling, run multiple cron jobs with different
# GITHUB_AGENT_WORKROOT values and max_tasks=1. Claiming is retried on
# git push conflicts so parallel pollers do not process the same task.

if [ $# -lt 2 ]; then
  echo "Usage: $0 owner/repo path/to/tasks.json [max_tasks]"
  exit 1
fi

REPO="$1"
TASK_FILE="$2"
MAX_TASKS="${3:-1}"
WORKROOT="${GITHUB_AGENT_WORKROOT:-$HOME/AIGC/agents/github-task-agent/repos}"
REPO_DIR="$WORKROOT/${REPO//\//__}"
PROMPT_FILE="$HOME/AIGC/agents/github-task-agent/prompts/polling-agent.md"

mkdir -p "$WORKROOT"

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
AGENT_NAME="${GITHUB_AGENT_NAME:-$HOSTNAME}"

# ── Claim pending tasks with push-conflict retry ───────────────────────────────
# Multiple cron agents may poll at the same time. Each one reads origin/latest,
# marks up to $MAX_TASKS pending tasks as running, commits, then pushes. If the
# push loses a race, reset to origin and retry so the next pending task is chosen.
CLAIMED=""
for attempt in 1 2 3; do
  sync_repo

  CLAIMED=$(python3 -c "
import json, datetime

task_file = '$TASK_FILE'
max_tasks = int('$MAX_TASKS')
agent_name = '$AGENT_NAME'

with open(task_file) as f:
    data = json.load(f)

tasks = [t for t in data.get('tasks', []) if t.get('status') == 'pending']
claimed = []
now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

for t in tasks[:max_tasks]:
    t['status'] = 'running'
    t['locked_by'] = agent_name
    t['locked_at'] = now
    t['updated_at'] = now
    claimed.append(t.get('id', ''))

if claimed:
    data['updated_at'] = now
    with open(task_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    for tid in claimed:
        if tid:
            print(tid)
" 2>/dev/null)

  if [ -z "$CLAIMED" ]; then
    echo "No pending tasks — exiting."
    exit 0
  fi

  echo "Claim attempt $attempt: $CLAIMED"
  git add "$TASK_FILE"
  git commit -m "chore(agent): claim tasks $(echo $CLAIMED | tr ' ' ',')"

  if git push origin "$DEFAULT_BRANCH"; then
    echo "Claimed: $CLAIMED"
    break
  fi

  echo "Claim push conflict, retrying..."
  git reset --hard "origin/$DEFAULT_BRANCH"
  CLAIMED=""
done

if [ -z "$CLAIMED" ]; then
  echo "Failed to claim tasks after retries."
  exit 1
fi

# ── Detect stale running tasks (crashed agent recovery) ───────────────────────
STALE=$(python3 -c "
import json, datetime

with open('$TASK_FILE') as f:
    data = json.load(f)

now = datetime.datetime.now(datetime.timezone.utc)
for t in data.get('tasks', []):
    if t.get('status') == 'running' and t.get('locked_at'):
        locked = datetime.datetime.fromisoformat(t['locked_at'].replace('Z', '+00:00'))
        age = (now - locked).total_seconds()
        if age > 600:
            print(t.get('id', ''))
" 2>/dev/null)

for stale_id in $STALE; do
  echo "Stale task detected: $stale_id — will be retried on next run"
done

# ── Spawn background hermes for each claimed task ─────────────────────────────
LOGDIR="$HOME/AIGC/agents/github-task-agent/logs"
mkdir -p "$LOGDIR"

echo "$CLAIMED" | while IFS= read -r TASK_ID; do
  [ -z "$TASK_ID" ] && continue
  LOGFILE="$LOGDIR/${TASK_ID}.log"

  PROMPT=$(cat <<'HEREDOC'
请读取 __PROMPT_FILE__ 作为完整流程指南。

本轮配置：
- Repository: __REPO__
- Local repo path: __REPO_DIR__
- Task file: __TASK_FILE__
- Default branch: __DEFAULT_BRANCH__

重要：请只处理 task id: __TASK_ID__，其他任务不要动。

请进入 Local repo path，读取 Task file，找到 status=running 且 id=__TASK_ID__ 的任务，完成后改为 completed/failed/blocked 并提交。如果是代码开发任务，创建独立功能分支和 PR。如果是内容/媒体任务，优先保存到 /Users/koopos/AIGC/ 对应目录，必要时再提交 repo。
HEREDOC
)

  PROMPT="${PROMPT//__PROMPT_FILE__/$PROMPT_FILE}"
  PROMPT="${PROMPT//__REPO__/$REPO}"
  PROMPT="${PROMPT//__REPO_DIR__/$REPO_DIR}"
  PROMPT="${PROMPT//__TASK_FILE__/$TASK_FILE}"
  PROMPT="${PROMPT//__DEFAULT_BRANCH__/$DEFAULT_BRANCH}"
  PROMPT="${PROMPT//__TASK_ID__/$TASK_ID}"

  nohup hermes chat -q "$PROMPT" -Q > "$LOGFILE" 2>&1 &
  echo "Spawned hermes for $TASK_ID (PID=$!) → $LOGFILE"
done

echo "All workers spawned — exiting."
