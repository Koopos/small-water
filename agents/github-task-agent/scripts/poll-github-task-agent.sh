#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./poll-github-task-agent.sh owner/repo .agent/tasks.json
#
# This script is intentionally small. The actual reasoning and task execution
# are delegated to Hermes. It pulls the repo, asks Hermes to process at most one
# pending task, then Hermes is responsible for committing status updates.

if [ $# -lt 2 ]; then
  echo "Usage: $0 owner/repo path/to/tasks.json"
  exit 1
fi

REPO="$1"
TASK_FILE="$2"
WORKROOT="${GITHUB_AGENT_WORKROOT:-$HOME/AIGC/agents/github-task-agent/repos}"
REPO_DIR="$WORKROOT/${REPO//\//__}"
PROMPT_FILE="$HOME/AIGC/agents/github-task-agent/prompts/polling-agent.md"

mkdir -p "$WORKROOT"

if [ ! -d "$REPO_DIR/.git" ]; then
  gh repo clone "$REPO" "$REPO_DIR"
fi

cd "$REPO_DIR"

git fetch origin --prune
DEFAULT_BRANCH=$(gh repo view "$REPO" --json defaultBranchRef -q '.defaultBranchRef.name')
git checkout "$DEFAULT_BRANCH"
git pull --ff-only origin "$DEFAULT_BRANCH"

if [ ! -f "$TASK_FILE" ]; then
  echo "Task file not found: $TASK_FILE"
  exit 0
fi

BASE_PROMPT=$(cat "$PROMPT_FILE")

hermes chat -q "$BASE_PROMPT

本轮配置：

Repository: $REPO
Local repo path: $REPO_DIR
Task file: $TASK_FILE
Default branch: $DEFAULT_BRANCH

请进入 Local repo path，读取 Task file，只处理一个 pending 任务。处理前先把任务改为 running 并提交；处理完成后改为 completed/failed/blocked 并提交。如果是代码开发任务，创建独立功能分支和 PR。如果是内容/媒体任务，优先保存到 /Users/koopos/AIGC/ 对应目录，必要时再提交 repo。"
