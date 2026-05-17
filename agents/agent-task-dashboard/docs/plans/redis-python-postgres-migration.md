# Queue + Worker Stack Migration Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Replace the current GitHub-file polling flow with a real task system: Next.js frontend, Node.js/TypeScript API, Redis queue, Python workers, and PostgreSQL persistence.

**Architecture:** Next.js remains the UI layer and talks to a Node.js/TypeScript API. The API owns task creation, leasing, state transitions, and result persistence in PostgreSQL. Redis is the queue/lease layer that prevents duplicate dispatch, and Python workers consume claimed jobs, execute them, then call back into the API to finalize status and artifacts.

**Tech Stack:** Next.js, Node.js/TypeScript, Redis, Python, PostgreSQL, Prisma (or equivalent DB layer), background worker process, REST API.

---

### Task 1: Define the task lifecycle and schema

**Objective:** Make task states, lease fields, retry policy, and worker affinity explicit in the database.

**Files:**
- Modify: `prisma/schema.prisma`
- Modify: `src/lib/task-types.ts`
- Modify: `src/lib/json.ts` if needed for payload helpers

**Step 1: Write failing validation tests or type checks**

Add schema expectations for:
- `pending -> running -> done/failed/blocked`
- `lockedBy`, `lockedAt`, `leaseExpiresAt`
- `workerPool` or equivalent routing field
- `retryCount`, `lastError`

**Step 2: Run checks to verify failure**

Run: `npm run lint`
Expected: fail until schema + types align.

**Step 3: Implement the minimal schema change**

Add the queue-related fields and indexes needed for lease-based dispatch.

**Step 4: Verify**

Run: `npm run lint`
Expected: pass.

---

### Task 2: Build the Node.js API for enqueue/claim/complete

**Objective:** Move queue ownership into the API so the frontend and workers never race on GitHub files.

**Files:**
- Create: `src/app/api/tasks/route.ts`
- Create: `src/app/api/tasks/[id]/claim/route.ts`
- Create: `src/app/api/tasks/[id]/complete/route.ts`
- Create: `src/app/api/tasks/[id]/fail/route.ts`
- Modify: `src/app/actions.ts`

**Step 1: Write failing API tests or route-level smoke tests**

Cover:
- create task
- claim task once
- reject double-claim
- complete task
- fail task

**Step 2: Run tests to verify failure**

Run the relevant test command or route smoke script.
Expected: routes missing or behavior failing.

**Step 3: Implement the API routes**

Use PostgreSQL for source of truth and Redis for lease coordination.

**Step 4: Verify**

Run the route tests again.
Expected: pass.

---

### Task 3: Add Redis-backed scheduler/lease logic

**Objective:** Prevent duplicate execution with a single lease authority.

**Files:**
- Create: `src/lib/queue.ts`
- Create: `src/lib/lease.ts`
- Modify: `src/lib/github-sync.ts` or remove GitHub-sync responsibilities from scheduling

**Step 1: Write a small regression test for lease acquisition**

Assert:
- pending task can be leased once
- expired lease is reclaimable
- active lease blocks other claims

**Step 2: Run the test to confirm failure**

Expected: no Redis lease layer yet.

**Step 3: Implement lease primitives**

Add atomic claim/release operations using Redis.

**Step 4: Verify**

Run the lease tests again.
Expected: pass.

---

### Task 4: Implement Python worker execution

**Objective:** Create a worker process that fetches a leased job, executes it, and writes back result state.

**Files:**
- Create: `worker/requirements.txt`
- Create: `worker/main.py`
- Create: `worker/executors/*.py`
- Create: `worker/README.md`

**Step 1: Write a minimal worker test**

Cover:
- claim from Redis
- execute one task payload
- post completion callback

**Step 2: Run the test to confirm failure**

Expected: worker code missing.

**Step 3: Implement the worker loop**

Support separate executors for:
- code
- image
- content

**Step 4: Verify**

Run the worker test and one local task simulation.
Expected: pass.

---

### Task 5: Refactor the Next.js frontend to reflect the real queue

**Objective:** Show pending/running/done tasks from PostgreSQL and let users create tasks without touching GitHub files.

**Files:**
- Modify: `src/app/page.tsx`
- Modify: `src/app/projects/page.tsx`
- Modify: `src/app/projects/[id]/page.tsx`
- Modify: `src/app/projects/new/page.tsx`
- Modify: `src/app/projects/[id]/CreateTaskForm.tsx`
- Modify: `src/app/tasks/[id]/page.tsx`

**Step 1: Write UI expectations**

Confirm the UI shows:
- queue state
- lease owner
- retry count
- error message
- worker pool

**Step 2: Run lint to confirm current UI copy is stale**

Expected: after schema/API changes, some props will be missing.

**Step 3: Update the UI**

Remove GitHub-file polling language and replace it with queue/worker language.

**Step 4: Verify**

Run `npm run lint` and manual page checks.
Expected: pass.

---

### Task 6: Migration and verification

**Objective:** Keep the old GitHub-sync path only as an optional import/export bridge, not as the main queue.

**Files:**
- Modify: `README.md`
- Modify: `POLLING_MODE.md`
- Modify: `github-task-agent/*` scripts only if they remain as compatibility tooling

**Step 1: Add migration notes**

Document:
- Redis is the queue
- PostgreSQL is the source of truth
- Python worker executes jobs
- GitHub is optional for code/artifact sync, not task locking

**Step 2: Run the full verification set**

Run:
- `npm run lint`
- `npm run build`
- worker smoke test
- API smoke test

**Step 3: Final sanity check**

Make sure no cron loop can start duplicate workers.

---

## Execution order

1. Schema / state model
2. API / claim endpoints
3. Redis lease layer
4. Python worker
5. Next.js UI updates
6. Documentation and migration cleanup
