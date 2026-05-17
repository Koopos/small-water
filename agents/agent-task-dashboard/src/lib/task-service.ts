import { nanoid } from "nanoid";
import { prisma } from "@/lib/prisma";
import { getRedis } from "@/lib/redis";
import { getWorkerPoolForType, queueScore, type WorkerPool, WORKER_POOLS } from "@/lib/task-routing";

const QUEUE_PREFIX = "agent-task-queue";
const LEASE_PREFIX = "agent-task-lease";
const DEFAULT_LEASE_MS = Number(process.env.AGENT_TASK_LEASE_MS ?? 10 * 60 * 1000);
const DEFAULT_RECLAIM_LIMIT = Number(process.env.AGENT_TASK_RECLAIM_LIMIT ?? 100);

export interface TaskInput {
  projectId: string;
  taskKey: string;
  type: string;
  priority: string;
  title: string;
  description: string;
  acceptanceCriteria: string;
  inputJson: string;
  outputJson?: string;
  artifactsJson?: string;
  workerPool?: WorkerPool;
}

export interface ClaimResult {
  taskId: string;
  workerPool: WorkerPool;
  leaseToken: string;
  leaseExpiresAt: string;
}

function queueKey(pool: WorkerPool) {
  return `${QUEUE_PREFIX}:${pool}`;
}

function leaseKey(taskId: string) {
  return `${LEASE_PREFIX}:${taskId}`;
}

function serializeLease(payload: ClaimResult) {
  return JSON.stringify(payload);
}

function deserializeDate(value: string | Date | null | undefined) {
  if (!value) return null;
  return value instanceof Date ? value : new Date(value);
}

export async function enqueueTaskToRedis(task: {
  id: string;
  priority: string;
  workerPool: WorkerPool | string;
  queuedAt?: Date | null;
  createdAt?: Date;
}) {
  const redis = await getRedis();
  const timestamp = task.queuedAt ?? task.createdAt ?? new Date();
  await redis.zAdd(queueKey(task.workerPool as WorkerPool), [
    { score: queueScore(task.priority, timestamp), value: task.id },
  ]);
}

export async function removeTaskFromRedis(taskId: string, workerPool?: WorkerPool) {
  const redis = await getRedis();
  if (workerPool) {
    await redis.zRem(queueKey(workerPool), taskId);
    return;
  }
  await Promise.all(WORKER_POOLS.map((pool) => redis.zRem(queueKey(pool), taskId)));
}

export async function createTaskRecord(data: TaskInput) {
  const workerPool = data.workerPool ?? getWorkerPoolForType(data.type);
  const task = await prisma.task.create({
    data: {
      projectId: data.projectId,
      taskKey: data.taskKey,
      type: data.type,
      workerPool,
      status: "pending",
      priority: data.priority,
      title: data.title,
      description: data.description,
      acceptanceCriteria: data.acceptanceCriteria,
      inputJson: data.inputJson,
      outputJson: data.outputJson ?? "{}",
      artifactsJson: data.artifactsJson ?? "[]",
      queuedAt: new Date(),
    },
  });

  await enqueueTaskToRedis(task);
  return task;
}

export async function resetTaskToPending(taskId: string) {
  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task) return null;

  await prisma.task.update({
    where: { id: taskId },
    data: {
      status: "pending",
      error: null,
      lastError: null,
      startedAt: null,
      completedAt: null,
      lockedBy: null,
      lockedAt: null,
      leaseToken: null,
      leaseExpiresAt: null,
    },
  });

  await enqueueTaskToRedis(task);
  return task;
}

export async function syncProjectTaskQueue(projectId: string) {
  const tasks = await prisma.task.findMany({
    where: { projectId },
    select: {
      id: true,
      priority: true,
      workerPool: true,
      status: true,
      queuedAt: true,
      createdAt: true,
    },
  });

  for (const task of tasks) {
    await removeTaskFromRedis(task.id);

    if (task.status === "pending") {
      await enqueueTaskToRedis({
        id: task.id,
        priority: task.priority,
        workerPool: task.workerPool as WorkerPool,
        queuedAt: task.queuedAt,
        createdAt: task.createdAt,
      });
    }
  }
}

export async function claimNextTask(pool: WorkerPool, workerId: string, leaseMs = DEFAULT_LEASE_MS) {
  const redis = await getRedis();
  const key = queueKey(pool);

  for (let attempt = 0; attempt < 25; attempt += 1) {
    const popped = await redis.zPopMin(key, 1);
    const item = Array.isArray(popped) ? popped[0] : popped;
    if (!item) return null;

    const taskId = item.value;
    const task = await prisma.task.findUnique({ where: { id: taskId } });
    if (!task || task.status !== "pending" || task.workerPool !== pool) {
      continue;
    }

    const leaseToken = nanoid(24);
    const leaseExpiresAt = new Date(Date.now() + leaseMs);
    const updated = await prisma.task.update({
      where: { id: taskId },
      data: {
        status: "running",
        lockedBy: workerId,
        lockedAt: new Date(),
        leaseToken,
        leaseExpiresAt,
        startedAt: task.startedAt ?? new Date(),
        retryCount: task.retryCount + 1,
        lastError: null,
      },
    });

    const claim: ClaimResult = {
      taskId: updated.id,
      workerPool: pool,
      leaseToken,
      leaseExpiresAt: leaseExpiresAt.toISOString(),
    };
    await redis.set(leaseKey(taskId), serializeLease(claim), { PX: leaseMs });
    return { task: updated, claim };
  }

  return null;
}

export async function extendTaskLease(taskId: string, workerId: string, leaseToken: string, leaseMs = DEFAULT_LEASE_MS) {
  const redis = await getRedis();
  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task || task.lockedBy !== workerId || task.leaseToken !== leaseToken) {
    return null;
  }

  const leaseExpiresAt = new Date(Date.now() + leaseMs);
  await prisma.task.update({
    where: { id: taskId },
    data: { leaseExpiresAt },
  });
  await redis.set(
    leaseKey(taskId),
    serializeLease({
      taskId,
      workerPool: task.workerPool as WorkerPool,
      leaseToken,
      leaseExpiresAt: leaseExpiresAt.toISOString(),
    }),
    { PX: leaseMs },
  );
  return leaseExpiresAt;
}

function extractRunLogContent(payload: Record<string, unknown>, fallbackError: string | null = null) {
  const stdout = typeof payload.stdout === "string" ? payload.stdout : typeof payload.output === "string" ? payload.output : null;
  const stderr = typeof payload.stderr === "string" ? payload.stderr : fallbackError;
  return { stdout, stderr };
}

function extractGitMetadata(payload: Record<string, unknown>, task: { branch: string | null; prUrl: string | null; githubCommitSha: string | null }) {
  return {
    branch: typeof payload.branch === "string" ? payload.branch : task.branch,
    prUrl: typeof payload.pr_url === "string" ? payload.pr_url : task.prUrl,
    githubCommitSha:
      typeof payload.github_commit_sha === "string"
        ? payload.github_commit_sha
        : typeof payload.githubCommitSha === "string"
          ? payload.githubCommitSha
          : task.githubCommitSha,
  };
}

export async function completeTask(taskId: string, workerId: string, payload: Record<string, unknown> = {}) {
  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task) throw new Error("Task not found");
  if (task.lockedBy && task.lockedBy !== workerId) throw new Error("Task is locked by another worker");

  const runId = nanoid();
  const { stdout, stderr } = extractRunLogContent(payload);
  const gitMetadata = extractGitMetadata(payload, task);

  await prisma.$transaction([
    prisma.task.update({
      where: { id: taskId },
      data: {
        status: "completed",
        outputJson: JSON.stringify(payload, null, 2),
        error: null,
        lastError: null,
        completedAt: new Date(),
        lockedBy: null,
        lockedAt: null,
        leaseToken: null,
        leaseExpiresAt: null,
        branch: gitMetadata.branch,
        prUrl: gitMetadata.prUrl,
        githubCommitSha: gitMetadata.githubCommitSha,
      },
    }),
    prisma.runLog.create({
      data: {
        projectId: task.projectId,
        taskId: task.id,
        runId,
        status: "completed",
        stdout: stdout ?? JSON.stringify(payload, null, 2),
        stderr,
      },
    }),
  ]);

  const redis = await getRedis();
  await redis.del(leaseKey(taskId));
}

export async function failTask(taskId: string, workerId: string, error: string, payload: Record<string, unknown> = {}) {
  const task = await prisma.task.findUnique({ where: { id: taskId } });
  if (!task) throw new Error("Task not found");
  if (task.lockedBy && task.lockedBy !== workerId) throw new Error("Task is locked by another worker");

  const runId = nanoid();
  const { stdout, stderr } = extractRunLogContent(payload, error);

  await prisma.$transaction([
    prisma.task.update({
      where: { id: taskId },
      data: {
        status: "failed",
        error,
        lastError: error,
        outputJson: JSON.stringify(payload, null, 2),
        completedAt: new Date(),
        lockedBy: null,
        lockedAt: null,
        leaseToken: null,
        leaseExpiresAt: null,
      },
    }),
    prisma.runLog.create({
      data: {
        projectId: task.projectId,
        taskId: task.id,
        runId,
        status: "failed",
        stdout,
        stderr: stderr ?? error,
      },
    }),
  ]);

  const redis = await getRedis();
  await redis.del(leaseKey(taskId));
}

export async function requeueExpiredTasks(limit = DEFAULT_RECLAIM_LIMIT) {
  const now = new Date();
  const expired = await prisma.task.findMany({
    where: {
      status: "running",
      leaseExpiresAt: { lt: now },
    },
    take: limit,
    orderBy: { leaseExpiresAt: "asc" },
  });

  for (const task of expired) {
    await prisma.task.update({
      where: { id: task.id },
      data: {
        status: "pending",
        error: task.error ?? "Lease expired; task returned to queue",
        lastError: task.error ?? "Lease expired; task returned to queue",
        lockedBy: null,
        lockedAt: null,
        leaseToken: null,
        leaseExpiresAt: null,
        startedAt: null,
      },
    });
    await enqueueTaskToRedis(task as { id: string; priority: string; workerPool: WorkerPool | string; queuedAt?: Date | null; createdAt?: Date });
  }

  return expired.length;
}

export function taskLeaseFromJson(value: string | null | undefined) {
  if (!value) return null;
  try {
    return JSON.parse(value) as ClaimResult;
  } catch {
    return null;
  }
}

export function normalizeDate(value: string | Date | null | undefined) {
  return deserializeDate(value);
}
