# Agent Task Dashboard MVP Plan

> 目标：做一个前端/后端管理系统，让用户不需要手改 .agent/tasks.json，也能安全地通过 GitHub 文件轮询模式管理本地 Agent 任务。

## Phase 1: 基础项目

### Task 1: 创建 Next.js 项目

技术：

- Next.js App Router
- TypeScript
- Tailwind CSS
- SQLite
- Prisma

命令：

```bash
npx create-next-app@latest agent-task-dashboard --typescript --tailwind --eslint --app
cd agent-task-dashboard
npm install prisma @prisma/client zod nanoid
npx prisma init --datasource-provider sqlite
```

### Task 2: 建数据库模型

模型：

- Project
- Task
- Artifact
- RunLog

### Task 3: 实现项目管理 API

API：

- GET /api/projects
- POST /api/projects
- GET /api/projects/:id
- PATCH /api/projects/:id

### Task 4: 实现任务管理 API

API：

- GET /api/projects/:id/tasks
- POST /api/projects/:id/tasks
- GET /api/tasks/:id
- PATCH /api/tasks/:id
- POST /api/tasks/:id/retry
- POST /api/tasks/:id/cancel

### Task 5: 实现 GitHub tasks.json 同步

功能：

- 从数据库导出 .agent/tasks.json
- commit + push 到 GitHub
- 从 GitHub pull 最新 .agent/tasks.json
- 更新数据库任务状态

### Task 6: 实现前端页面

页面：

- /projects
- /projects/new
- /projects/[id]
- /tasks/[id]

### Task 7: 创建任务表单

按任务类型动态显示表单：

- agent-dev
- agent-image
- agent-video-script
- agent-article
- agent-hot-content

### Task 8: 任务看板

列：

- pending
- running
- blocked
- failed
- completed

### Task 9: 任务详情页

展示：

- 输入
- 验收标准
- 状态
- 输出
- PR
- 产物
- 错误
- 日志

### Task 10: 手动同步按钮

按钮：

- Sync to GitHub
- Sync from GitHub
- Poll once

## Phase 2: 体验增强

- 图片产物预览
- Markdown 脚本预览
- PR 状态同步
- 执行日志 tail
- 任务复制
- 任务模板
- 批量创建任务

## Phase 3: 安全增强

- 任务审批
- 禁止路径配置
- 允许任务类型白名单
- 每轮最大任务数
- 最大执行时长
- GitHub token 权限检查

