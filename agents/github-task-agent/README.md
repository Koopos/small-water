# GitHub 多任务 Agent 使用说明

## 1. Label 约定

在 GitHub Issue 上使用这些 label 触发不同任务：

- agent-task：通用任务
- agent-dev：代码开发任务
- agent-image：生图任务
- agent-video-script：视频脚本任务
- agent-article：图文文章任务
- agent-hot-content：热点图文任务
- agent-dating-post：相亲图文任务（只填标题和优先级）

## 2. 推荐 Issue 标题

代码开发：

feat: 增加宝宝成长记录页面

生图：

image: 生成公众号封面图《AI Agent 自动开发》

视频脚本：

script: 生成 60 秒短视频脚本《普通人如何用 AI Agent》

图文热文：

article: 写一篇小红书图文《AI Agent 正在改变个人生产力》

## 3. Webhook 状态

本机已启用 Hermes webhook 配置：

host: 0.0.0.0
port: 8644

已创建 subscription：

name: github-task-agent
local URL: http://localhost:8644/webhooks/github-task-agent
secret: 768othPlwoTfVwLvS9SExsYGDFua1wQQNYaLjvsQt5I
events: issues

注意：当前已有一个 Hermes Gateway 进程在运行，但它可能还没加载刚写入的 webhook 配置。需要你在终端手动执行一次：

hermes gateway restart

如果 restart 被权限确认拦住，可以执行：

hermes gateway run --replace

健康检查：

curl http://localhost:8644/health

## 4. 创建 webhook subscription

我已经创建好了。如果以后要重建，可以把 prompts/router.md 内容作为 --prompt 创建订阅。

示例：

PROMPT=$(cat /Users/koopos/AIGC/agents/github-task-agent/prompts/router.md)
hermes webhook subscribe github-task-agent \
  --events "issues" \
  --skills "github-pr-workflow,writing-plans,subagent-driven-development,baoyu-cover-image,baoyu-infographic,short-video-script" \
  --prompt "$PROMPT" \
  --description "GitHub Issue driven multi-task agent: code, image, video script, articles"

然后到 GitHub repo Settings -> Webhooks 添加：

Payload URL:
http://你的机器或公网域名:8644/webhooks/github-task-agent

Content type:
application/json

Secret:
使用 hermes webhook subscribe 输出的 secret

Events:
Issues

## 5. 如果本机没有公网地址

可以用 cloudflared 或 ngrok 暴露：

cloudflared tunnel --url http://localhost:8644

然后用 cloudflared 输出的 https 地址作为 GitHub webhook Payload URL。
