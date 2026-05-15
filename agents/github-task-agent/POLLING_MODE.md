# GitHub 文件轮询式本地 Agent

这个方案不用 GitHub Webhook，不需要把本地端口暴露到公网。

工作方式：

1. 你在 GitHub 仓库里维护一个任务文件，例如：.agent/tasks.json
2. 本地 Agent 每 15 分钟 git pull 一次仓库
3. Agent 找到 status=pending 的任务
4. Agent 先把任务改成 running 并提交回 GitHub，表示已领取
5. Agent 执行任务
6. Agent 完成后把任务改成 completed / failed / blocked，并提交回 GitHub

优点：

- 不开放公网端口
- GitHub 不能主动打到你本机
- 所有任务都有状态记录
- 你可以通过改 GitHub 文件来控制 Agent
- 出问题可以直接把任务状态改成 blocked/disabled 或暂停本地 cron

## 文件

任务模板：

/Users/koopos/AIGC/agents/github-task-agent/templates/tasks.json

轮询 Agent prompt：

/Users/koopos/AIGC/agents/github-task-agent/prompts/polling-agent.md

轮询脚本：

/Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh

## 在你的仓库里添加任务文件

把模板复制到仓库：

mkdir -p .agent
cp /Users/koopos/AIGC/agents/github-task-agent/templates/tasks.json .agent/tasks.json
git add .agent/tasks.json
git commit -m "chore(agent): add task queue"
git push

## 手动跑一次

/Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh owner/repo .agent/tasks.json

把 owner/repo 换成你的仓库，例如：

/Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh Koopos/my-repo .agent/tasks.json

## 每 15 分钟自动跑

可以用 Hermes cronjob，也可以用系统 cron。

Hermes cronjob 推荐：

hermes cron create "every 15m"

Prompt 填：

运行 /Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh owner/repo .agent/tasks.json，处理一个 pending 任务。不要开放 webhook。执行后汇报 task id、状态、PR 或产物路径。

如果用系统 cron：

*/15 * * * * /Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh owner/repo .agent/tasks.json >> /Users/koopos/AIGC/agents/github-task-agent/poll.log 2>&1

## 任务类型

支持：

- agent-dev：代码开发
- agent-image：生图
- agent-video-script：视频脚本
- agent-article：图文文章
- agent-hot-content：图文热文/热点内容
- agent-dating-post：相亲图文（只需标题和优先级）

## 状态

- pending：等待处理
- running：正在处理
- completed：完成
- failed：失败
- blocked：需求不清楚或需要人工确认

## 建议

为了安全，建议：

1. 单轮只处理一个任务
2. 不自动 merge PR
3. 不直接改 main/master
4. 不执行任务文件里写的任意 shell 命令
5. 媒体任务先保存到 /Users/koopos/AIGC/，需要入库时再开 PR
6. 先在测试仓库跑通，再接入正式仓库
