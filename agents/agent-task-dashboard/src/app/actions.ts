"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { nanoid } from "nanoid";
import { prisma } from "@/lib/prisma";
import { pollProjectOnce, syncProjectFromGitHub, syncProjectToGitHub } from "@/lib/github-sync";
import { linesToJsonArray } from "@/lib/json";
import { createTaskRecord, removeTaskFromRedis, resetTaskToPending } from "@/lib/task-service";
import { getWorkerPoolForType } from "@/lib/task-routing";

function text(formData: FormData, key: string, fallback = "") {
  return String(formData.get(key) ?? fallback).trim();
}

export async function createProject(formData: FormData) {
  const fullName = text(formData, "fullName");
  const [owner, repo] = fullName.split("/").map((part) => part.trim());
  if (!owner || !repo) {
    throw new Error("GitHub 仓库格式必须是 owner/repo");
  }

  const project = await prisma.project.create({
    data: {
      name: text(formData, "name", repo) || repo,
      owner,
      repo,
      defaultBranch: text(formData, "defaultBranch", "main") || "main",
      taskFilePath: text(formData, "taskFilePath", ".agent/tasks.json") || ".agent/tasks.json",
      localPath: text(formData, "localPath") || null,
      pollIntervalMinutes: Number(text(formData, "pollIntervalMinutes", "15")) || 15,
    },
  });

  revalidatePath("/");
  redirect(`/projects/${project.id}`);
}

async function getOrCreateDefaultProject() {
  const existing = await prisma.project.findFirst({
    where: {
      owner: "local",
      repo: "task-inbox",
    },
  });

  if (existing) return existing;

  return prisma.project.create({
    data: {
      name: "默认任务池",
      owner: "local",
      repo: "task-inbox",
      defaultBranch: "main",
      taskFilePath: "N/A",
      localPath: null,
      pollIntervalMinutes: 10,
    },
  });
}

export async function createQuickTask(formData: FormData) {
  const project = await getOrCreateDefaultProject();
  const type = text(formData, "type", "agent-dating-post");
  const title = text(formData, "title");
  if (!title) throw new Error("任务标题不能为空");

  const taskKey = text(formData, "taskKey") || `task-${nanoid(8)}`;
  const repoName = text(formData, "repoName");
  const description = text(formData, "description");

  if (type === "agent-dev" && !repoName) {
    throw new Error("代码任务需要填写关联仓库或参考信息");
  }
  if ((type === "agent-dev" || type === "agent-image") && !description) {
    throw new Error("该类型任务需要填写详细需求");
  }

  const references: string[] = [];
  if (repoName) {
    references.push(repoName);
  }

  const input = {
    ...(type === "agent-dev" && { references }),
  };

  const task = await createTaskRecord({
    projectId: project.id,
    taskKey,
    type,
    workerPool: getWorkerPoolForType(type),
    priority: text(formData, "priority", "normal"),
    title,
    description,
    acceptanceCriteria: "[]",
    inputJson: JSON.stringify(input, null, 2),
    outputJson: "{}",
    artifactsJson: "[]",
  });

  revalidatePath("/");
  revalidatePath(`/projects/${project.id}`);
  revalidatePath("/projects");
  redirect(`/tasks/${task.id}`);
}

export async function createTask(projectId: string, formData: FormData) {
  const type = text(formData, "type", "agent-dating-post");
  const title = text(formData, "title");
  if (!title) throw new Error("任务标题不能为空");

  const taskKey = text(formData, "taskKey") || `task-${nanoid(8)}`;
  const repoName = text(formData, "repoName");
  const description = text(formData, "description");

  if (type === "agent-dev" && !repoName) {
    throw new Error("代码开发任务需要填写仓库名");
  }
  if ((type === "agent-dev" || type === "agent-image") && !description) {
    throw new Error("该类型任务需要填写详细需求");
  }

  const references: string[] = [];
  if (repoName) {
    references.push(repoName);
  }

  const input = {
    ...(type === "agent-dev" && { references }),
  };

  await createTaskRecord({
    projectId,
    taskKey,
    type,
    workerPool: getWorkerPoolForType(type),
    priority: text(formData, "priority", "normal"),
    title,
    description,
    acceptanceCriteria: "[]",
    inputJson: JSON.stringify(input, null, 2),
    outputJson: "{}",
    artifactsJson: "[]",
  });

  revalidatePath(`/projects/${projectId}`);
  redirect(`/projects/${projectId}`);
}

export async function updateTaskStatus(taskId: string, status: string) {
  const task = await prisma.task.findUniqueOrThrow({ where: { id: taskId } });

  if (status === "pending") {
    await resetTaskToPending(taskId);
  } else if (["completed", "failed", "blocked"].includes(status)) {
    await prisma.task.update({
      where: { id: taskId },
      data: {
        status,
        error: status === "blocked" ? task.error : null,
        lastError: task.lastError,
        completedAt: new Date(),
        lockedBy: null,
        lockedAt: null,
        leaseToken: null,
        leaseExpiresAt: null,
      },
    });
    await removeTaskFromRedis(taskId, task.workerPool as "code" | "image" | "content");
  } else {
    await prisma.task.update({ where: { id: taskId }, data: { status } });
  }

  revalidatePath(`/projects/${task.projectId}`);
  revalidatePath(`/tasks/${taskId}`);
}

export async function updateTask(taskId: string, formData: FormData) {
  const task = await prisma.task.findUniqueOrThrow({ where: { id: taskId }, select: { projectId: true } });
  const type = text(formData, "type", "agent-dev");
  const status = text(formData, "status", "pending");
  const input = {
    style: text(formData, "style") || undefined,
    platform: text(formData, "platform") || undefined,
    duration: text(formData, "duration") || undefined,
    aspect_ratio: text(formData, "aspectRatio") || undefined,
    references: text(formData, "references")
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean),
    require_screenshot: formData.get("requireScreenshot") === "on",
    auto_pr: formData.get("autoPr") !== "off",
  };

  await prisma.task.update({
    where: { id: taskId },
    data: {
      type,
      status,
      priority: text(formData, "priority", "normal"),
      title: text(formData, "title"),
      description: text(formData, "description"),
      acceptanceCriteria: linesToJsonArray(text(formData, "acceptanceCriteria")),
      inputJson: JSON.stringify(input, null, 2),
      error: status === "pending" ? null : text(formData, "error") || null,
      startedAt: status === "pending" ? null : undefined,
      completedAt: status === "pending" ? null : undefined,
      lockedBy: status === "pending" ? null : undefined,
      lockedAt: status === "pending" ? null : undefined,
    },
  });

  revalidatePath(`/projects/${task.projectId}`);
  revalidatePath(`/tasks/${taskId}`);
}

export async function deleteTask(taskId: string) {
  const task = await prisma.task.findUniqueOrThrow({ where: { id: taskId }, select: { projectId: true, workerPool: true } });
  await removeTaskFromRedis(taskId, task.workerPool as "code" | "image" | "content");
  await prisma.task.delete({ where: { id: taskId } });
  revalidatePath(`/projects/${task.projectId}`);
  redirect(`/projects/${task.projectId}`);
}

export async function syncToGitHub(projectId: string) {
  await syncProjectToGitHub(projectId);
  revalidatePath(`/projects/${projectId}`);
}

export async function syncFromGitHub(projectId: string) {
  const SYNC_TIMEOUT = 15_000;
  await Promise.race([
    syncProjectFromGitHub(projectId),
    new Promise((_, reject) => setTimeout(() => reject(new Error("从 GitHub 同步超时（15s）")), SYNC_TIMEOUT)),
  ]);
  revalidatePath(`/projects/${projectId}`);
}

export async function pollOnce(projectId: string) {
  const SYNC_TIMEOUT = 15_000;
  // Agent 处理后自动从 GitHub 同步最新状态
  await Promise.race([
    (async () => {
      await pollProjectOnce(projectId);
      await syncProjectFromGitHub(projectId);
    })(),
    new Promise((_, reject) => setTimeout(() => reject(new Error("同步超时（15s）")), SYNC_TIMEOUT)),
  ]);
  revalidatePath(`/projects/${projectId}`);
}

// 定时刷新 - 只刷新页面缓存，不做网络请求
export async function refreshProject(projectId: string) {
  revalidatePath(`/projects/${projectId}`);
}
