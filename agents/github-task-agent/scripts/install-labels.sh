#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 owner/repo"
  exit 1
fi

REPO="$1"

gh label create agent-task --repo "$REPO" --color "5319E7" --description "Generic task for autonomous agent" --force
gh label create agent-dev --repo "$REPO" --color "0E8A16" --description "Code development task for autonomous agent" --force
gh label create agent-image --repo "$REPO" --color "FBCA04" --description "Image generation task for autonomous agent" --force
gh label create agent-video-script --repo "$REPO" --color "1D76DB" --description "Video script generation task for autonomous agent" --force
gh label create agent-article --repo "$REPO" --color "C2E0C6" --description "Article / long-form content task for autonomous agent" --force
gh label create agent-hot-content --repo "$REPO" --color "D93F0B" --description "Hot-topic social content task for autonomous agent" --force
gh label create agent-dating-post --repo "$REPO" --color "F9D0EC" --description "Dating/emotional carousel post task" --force

echo "Labels installed for $REPO"
