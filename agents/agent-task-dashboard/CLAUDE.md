# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Agent Task Dashboard - a web interface for managing AI agent tasks with bidirectional GitHub synchronization. Tasks are stored locally in SQLite and synced to `.agent/tasks.json` files in GitHub repositories.

## Commands

```bash
npm run dev      # Start development server (http://localhost:3000)
npm run build    # Production build
npm run start    # Start production server
npm run lint     # Run ESLint

npx prisma generate    # Regenerate Prisma client after schema changes
npx prisma db push     # Apply schema changes to database
```

## Architecture

### Tech Stack
- **Framework**: Next.js 16 (App Router) with Turbopack
- **Database**: SQLite via Prisma + better-sqlite3 adapter
- **Styling**: Tailwind CSS v4 (CSS-based configuration)
- **UI Components**: lucide-react for icons
- **Validation**: Zod for runtime validation
- **ID Generation**: nanoid

### Directory Structure
```
src/
├── app/                    # Next.js App Router pages
│   ├── actions.ts         # Server Actions for mutations
│   ├── api/               # REST API routes (for external clients)
│   │   └── projects/      # Project/task CRUD endpoints
│   ├── projects/          # Project management pages
│   │   ├── [id]/page.tsx # Project detail with task board
│   │   └── new/          # Create project form
│   └── tasks/[id]/       # Task detail page
├── lib/
│   ├── prisma.ts         # Prisma client singleton
│   ├── github-sync.ts    # GitHub sync logic (git clone, pull, push)
│   ├── task-types.ts     # Task status/type constants & helpers
│   └── json.ts           # JSON parsing utilities
└── generated/prisma/      # Prisma-generated types (do not edit)
```

### Database Models
- **Project**: GitHub repo configuration, sync settings, local path
- **Task**: Agent task with status (pending/running/blocked/failed/completed), input/output JSON, artifacts
- **Artifact**: Generated assets linked to tasks
- **RunLog**: Poll execution history

### Server Actions Pattern
All mutations use Next.js Server Actions (`"use server"`):
- `createProject(formData)` - Add new GitHub project
- `createTask(projectId, formData)` - Create pending task
- `updateTaskStatus(taskId, status)` - Update task state
- `syncToGitHub(projectId)` / `syncFromGitHub(projectId)` - Bidirectional sync
- `pollOnce(projectId)` - Trigger agent poll script

### GitHub Sync Flow
1. `ensureRepo()` clones repo if needed, fetches latest
2. `syncProjectToGitHub()` writes `tasks.json` and commits
3. `syncProjectFromGitHub()` reads `tasks.json` and upserts tasks
4. External agent polls periodically via `poll-github-task-agent.sh`

### Key Patterns
- Prisma client uses singleton pattern with globalForPrisma for dev hot reload
- JSON fields stored as strings in SQLite (parsed at runtime)
- Task input/output use snake_case for GitHub JSON compatibility
- Status transitions update timestamps (startedAt, completedAt)
