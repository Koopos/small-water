export type WorkerPool = "code" | "image" | "content";

export const WORKER_POOLS: WorkerPool[] = ["code", "image", "content"];

export const TASK_TYPE_TO_POOL: Record<string, WorkerPool> = {
  "agent-dev": "code",
  "agent-image": "image",
  "agent-video-script": "content",
  "agent-article": "content",
  "agent-hot-content": "content",
  "agent-dating-post": "content",
  "agent-task": "content",
};

export function getWorkerPoolForType(type: string): WorkerPool {
  return TASK_TYPE_TO_POOL[type] ?? "content";
}

export function workerPoolLabel(pool: WorkerPool) {
  return ({
    code: "代码",
    image: "生图",
    content: "图文/脚本",
  } as const)[pool];
}

export function taskTypeToPoolLabel(type: string) {
  return workerPoolLabel(getWorkerPoolForType(type));
}

export function priorityRank(priority: string) {
  if (priority === "high") return 0;
  if (priority === "low") return 2;
  return 1;
}

export function queueScore(priority: string, timestamp: Date) {
  return priorityRank(priority) * 1_000_000_000_000_000 + timestamp.getTime();
}
