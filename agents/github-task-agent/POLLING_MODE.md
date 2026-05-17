# GitHub 文件调度式本地 Agent

这个方案把“调度”和“执行”拆开：

- scheduler：只负责扫描任务、抢锁、分配 worker pool
- worker：只负责执行一个已经被领取的任务

不要再用“3 个相同 agent + 不同 cron 间隔”去碰运气。一个 scheduler 就够了，worker 按任务类型分流。

## 工作方式

1. 你在 GitHub 仓库里维护一个任务文件，例如：.agent/tasks.json
2. scheduler 定时 git pull 仓库，扫描 status=pending 的任务
3. scheduler 按 worker pool 领取任务：
   - code：agent-dev
   - image：agent-image
   - content：agent-article / agent-hot-content / agent-video-script / agent-dating-post
4. scheduler 在提交前先把任务改成 running，并写 locked_by、locked_at
5. scheduler 只负责启动对应 worker，不直接处理业务
6. worker 读取自己被分配的 task id，完成后把任务改成 completed / failed / blocked，再提交回 GitHub
7. 如果 worker 超时没有回写，scheduler 会把 stale lock 重新释放回 pending

## 为什么这样更稳

- scheduler 只有一个，避免 cron 重叠
- 任务有锁，避免重复领取
- 不同任务类型分开并发，代码任务不会堵住图片/内容任务
- GitHub 只作为同步介质，不作为高频抢锁队列

## 文件

任务模板：

/Users/koopos/AIGC/agents/github-task-agent/templates/tasks.json

调度 prompt：

/Users/koopos/AIGC/agents/github-task-agent/prompts/polling-agent.md

调度脚本：

/Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh

worker 包装脚本：

/Users/koopos/AIGC/agents/github-task-agent/scripts/dispatch-task-worker.sh

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

## 每次只保留一个 cron

建议只保留一个 scheduler cron，例如每 30 秒或每 1 分钟运行一次。

Hermes cronjob 示例：

hermes cron create "every 1m"

Prompt 填：

运行 /Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh owner/repo .agent/tasks.json。它是 scheduler，只负责领取任务并分发 worker，不要再额外起多个相同 agent。执行后汇报：本轮领取的 task id、分发到的 worker pool、状态、PR 或产物路径。

如果用系统 cron：

* * * * * /Users/koopos/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh owner/repo .agent/tasks.json >> /Users/koopos/AIGC/agents/github-task-agent/poll.log 2>&1

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

1. scheduler 只保留 1 个
2. code worker 并发保持 1
3. image/content worker 分开限流，不要混跑
4. 不自动 merge PR
5. 不直接改 main/master
6. 不执行任务文件里写的任意 shell 命令
7. 媒体任务先保存到 /Users/koopos/AIGC/，需要入库时再开 PR
8. 先在测试仓库跑通，再接入正式仓库
