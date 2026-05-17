#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./dispatch-task-worker.sh owner/repo path/to/tasks.json task-id worker-pool default-branch
#
# This wrapper only launches the worker agent for one claimed task.
# The scheduler is responsible for claiming tasks and deciding which
# worker pool should handle them.

if [ $# -lt 5 ]; then
  echo "Usage: $0 owner/repo path/to/tasks.json task-id worker-pool default-branch"
  exit 1
fi

REPO="$1"
TASK_FILE="$2"
TASK_ID="$3"
WORKER_POOL="$4"
DEFAULT_BRANCH="$5"
WORKROOT="${GITHUB_AGENT_WORKROOT:-$HOME/AIGC/agents/github-task-agent/repos}"
REPO_DIR="$WORKROOT/${REPO//\//__}"
PROMPT_FILE="$HOME/AIGC/agents/github-task-agent/prompts/polling-agent.md"
LOGDIR="$HOME/AIGC/agents/github-task-agent/logs"

mkdir -p "$LOGDIR"

HOSTNAME="${HOSTNAME:-$(hostname)}"
AGENT_NAME="${GITHUB_AGENT_NAME:-$HOSTNAME}-$WORKER_POOL"
LOGFILE="$LOGDIR/${TASK_ID}.log"

PROMPT=$(cat <<'HEREDOC'
请读取 __PROMPT_FILE__ 作为完整流程指南。

本轮配置：
- Repository: __REPO__
- Local repo path: __REPO_DIR__
- Task file: __TASK_FILE__
- Worker pool: __WORKER_POOL__
- Worker name: __AGENT_NAME__
- Default branch: __DEFAULT_BRANCH__

重要：
- 只处理 task id: __TASK_ID__
- 不要检查、领取或修改其他任务
- 如果你发现当前 task 已不是 running，先停止并说明原因
- 只按任务文件里的内容执行
HEREDOC
)

PROMPT="${PROMPT//__PROMPT_FILE__/$PROMPT_FILE}"
PROMPT="${PROMPT//__REPO__/$REPO}"
PROMPT="${PROMPT//__REPO_DIR__/$REPO_DIR}"
PROMPT="${PROMPT//__TASK_FILE__/$TASK_FILE}"
PROMPT="${PROMPT//__WORKER_POOL__/$WORKER_POOL}"
PROMPT="${PROMPT//__AGENT_NAME__/$AGENT_NAME}"
PROMPT="${PROMPT//__DEFAULT_BRANCH__/$DEFAULT_BRANCH}"
PROMPT="${PROMPT//__TASK_ID__/$TASK_ID}"

nohup hermes chat -q "$PROMPT" -Q > "$LOGFILE" 2>&1 &
PID=$!

echo "Spawned $WORKER_POOL worker for $TASK_ID (PID=$PID) -> $LOGFILE"
