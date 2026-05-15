# GitHub 文件轮询式 Agent 管理后台方案

## 结论

不建议长期直接改 JSON。

JSON 文件适合做 MVP 的“任务队列存储”，但用户操作应该通过一个前端/后端管理系统完成：

- 前端：创建任务、查看状态、查看产物、暂停/取消/重试任务
- 后端：维护任务数据、生成 .agent/tasks.json、同步 GitHub、读取执行结果
- 本地 Agent：每 15 分钟拉 GitHub 的 .agent/tasks.json，处理 pending 任务，处理后提交状态

这样保留“安全的 GitHub 文件轮询模式”，同时用户不用手改 JSON。

---

## 推荐架构

```text
浏览器管理后台
    ↓
Backend API
    ↓
数据库 SQLite/Postgres
    ↓
GitHub Sync Worker
    ↓
GitHub Repo: .agent/tasks.json
    ↓ 每 15 分钟本地拉取
Local Agent Runner
    ↓
执行代码开发 / 生图 / 视频脚本 / 图文任务
    ↓
更新 .agent/tasks.json 并 push
    ↓
Backend 定时同步状态
    ↓
前端展示结果
```

---

## MVP 技术选型

为了最快落地，推荐：

- 前端：Next.js / React
- 后端：Next.js Route Handlers 或 FastAPI
- 数据库：SQLite 起步
- GitHub 操作：gh CLI 或 GitHub REST API
- 本地 Agent：继续用 Hermes CLI
- 任务同步：定时 cron / background worker

如果你想简单：一个 Next.js 全栈项目就够。

---

## 核心对象

### Project

一个 GitHub 仓库就是一个 Project。

字段：

- id
- name
- owner
- repo
- default_branch
- task_file_path，默认 .agent/tasks.json
- local_path
- enabled
- poll_interval_minutes，默认 15
- created_at
- updated_at

### Task

字段：

- id
- project_id
- task_key，例如 task-001
- type
- status
- priority
- title
- description
- acceptance_criteria
- input_json
- output_json
- error
- branch
- pr_url
- artifacts_json
- created_at
- started_at
- completed_at
- locked_by
- locked_at
- github_commit_sha

### Artifact

字段：

- id
- task_id
- type: image / markdown / screenshot / video / code-pr
- path
- url
- prompt
- metadata_json
- created_at

### RunLog

字段：

- id
- task_id
- run_id
- status
- stdout
- stderr
- started_at
- completed_at

---

## 页面设计

### 1. 项目列表页

功能：

- 添加 GitHub 仓库
- 显示仓库任务数量
- 显示最近同步时间
- 开启/暂停轮询

### 2. 项目详情页

模块：

- 任务看板：pending / running / blocked / failed / completed
- GitHub 同步状态
- 最近执行日志
- 任务文件路径

### 3. 创建任务页

根据任务类型显示不同表单：

#### 代码开发 agent-dev

- 标题
- 需求描述
- 验收标准
- 参考路径
- 禁止修改路径
- 是否需要截图
- 是否自动创建 PR

#### 生图 agent-image

- 主题
- 用途：封面/插图/海报/小红书/公众号
- 比例：square/portrait/landscape
- 风格
- 文案
- 参考图
- 禁忌

#### 视频脚本 agent-video-script

- 主题
- 平台
- 时长
- 受众
- 风格
- CTA

#### 图文热文 agent-hot-content

- 主题
- 平台
- 受众
- 语气
- 是否联网核实
- 是否生成配图 prompt

### 4. 任务详情页

功能：

- 查看任务完整输入
- 查看状态流转
- 查看 Agent 输出
- 查看 PR 链接
- 查看图片/脚本/截图产物
- Retry
- Cancel
- Mark blocked
- Clone task

### 5. 设置页

- GitHub token 状态
- 默认本地工作目录
- 默认轮询间隔
- Agent 命令
- 是否允许自动 PR
- 是否允许媒体任务提交 repo

---

## 后端 API 设计

### Projects

GET /api/projects
POST /api/projects
GET /api/projects/:id
PATCH /api/projects/:id
DELETE /api/projects/:id

### Tasks

GET /api/projects/:projectId/tasks
POST /api/projects/:projectId/tasks
GET /api/tasks/:id
PATCH /api/tasks/:id
POST /api/tasks/:id/cancel
POST /api/tasks/:id/retry
POST /api/tasks/:id/block

### Sync

POST /api/projects/:id/sync-to-github
POST /api/projects/:id/sync-from-github
POST /api/projects/:id/poll-once

### Artifacts

GET /api/tasks/:id/artifacts
GET /api/artifacts/:id

---

## 同步策略

### 创建任务

1. 用户在 Web UI 创建任务
2. 后端写入数据库
3. 后端生成/更新 .agent/tasks.json
4. 后端 commit + push 到 GitHub
5. 任务状态为 pending

### Agent 领取任务

1. 本地 Agent 每 15 分钟 git pull
2. 读取 .agent/tasks.json
3. 找到 pending 任务
4. 改成 running
5. commit + push

### Agent 完成任务

1. Agent 执行任务
2. 写 output、artifacts、error
3. 改成 completed/failed/blocked
4. commit + push

### 后端同步状态

1. 后端定时 pull GitHub
2. 读取 .agent/tasks.json
3. 更新数据库任务状态
4. 前端展示最新状态

---

## 为什么仍然保留 .agent/tasks.json

因为它是 GitHub 上的“安全任务协议文件”：

- 容易审计
- 可以 code review
- 可以回滚
- 不需要公网 webhook
- 不需要后端直接访问你本地电脑
- 本地 Agent 只信任这个文件

前端/后端只是帮你更方便地生成和管理它。

---

## MVP 范围

第一版只做：

1. 项目配置
2. 创建任务
3. 任务列表/详情
4. 同步任务到 GitHub .agent/tasks.json
5. 从 GitHub 读取状态
6. 本地轮询脚本执行任务
7. 展示 PR 和产物路径

暂时不做：

- 多用户权限
- 在线预览图片
- 自动合并 PR
- 复杂审批流
- 任务依赖 DAG
- 实时 WebSocket

---

## 推荐第一版界面

信息架构：

```text
左侧：Projects
中间：Tasks Kanban
右侧：Task Detail
顶部：New Task / Sync / Poll Once
```

视觉风格：

- 工具型产品，偏 Linear / GitHub Projects
- 浅色主题优先
- 状态颜色克制
- pending 灰色
- running 蓝色
- blocked 黄色
- failed 红色
- completed 绿色

---

## 下一步

如果要我继续执行，建议直接建一个项目：

agent-task-dashboard

第一阶段做 Next.js + SQLite MVP：

- 创建项目
- Prisma schema
- API routes
- 管理页面
- GitHub sync service
- 本地 poll runner 配置页

