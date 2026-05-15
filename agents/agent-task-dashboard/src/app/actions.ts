"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { nanoid } from "nanoid";
import { prisma } from "@/lib/prisma";
import { linesToJsonArray } from "@/lib/json";
import { pollProjectOnce, syncProjectFromGitHub, syncProjectToGitHub } from "@/lib/github-sync";

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

export async function createTask(projectId: string, formData: FormData) {
  const type = text(formData, "type", "agent-dev");
  const title = text(formData, "title");
  if (!title) throw new Error("任务标题不能为空");

  const taskKey = text(formData, "taskKey") || `task-${nanoid(8)}`;
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

  await prisma.task.create({
    data: {
      projectId,
      taskKey,
      type,
      status: "pending",
      priority: text(formData, "priority", "normal"),
      title,
      description: text(formData, "description"),
      acceptanceCriteria: linesToJsonArray(text(formData, "acceptanceCriteria")),
      inputJson: JSON.stringify(input, null, 2),
      outputJson: "{}",
      artifactsJson: "[]",
    },
  });

  revalidatePath(`/projects/${projectId}`);
  redirect(`/projects/${projectId}`);
}

export async function updateTaskStatus(taskId: string, status: string) {
  const data: { status: string; error?: string | null; completedAt?: Date | null; startedAt?: Date | null; lockedBy?: string | null; lockedAt?: Date | null } = { status };
  if (status === "pending") {
    data.error = null;
    data.completedAt = null;
    data.startedAt = null;
    data.lockedBy = null;
    data.lockedAt = null;
  }
  if (["completed", "failed", "blocked"].includes(status)) {
    data.completedAt = new Date();
  }
  await prisma.task.update({ where: { id: taskId }, data });
  const task = await prisma.task.findUniqueOrThrow({ where: { id: taskId }, select: { projectId: true } });
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
  const task = await prisma.task.findUniqueOrThrow({ where: { id: taskId }, select: { projectId: true } });
  await prisma.task.delete({ where: { id: taskId } });
  revalidatePath(`/projects/${task.projectId}`);
  redirect(`/projects/${task.projectId}`);
}

export async function syncToGitHub(projectId: string) {
  await syncProjectToGitHub(projectId);
  revalidatePath(`/projects/${projectId}`);
}

export async function syncFromGitHub(projectId: string) {
  await syncProjectFromGitHub(projectId);
  revalidatePath(`/projects/${projectId}`);
}

export async function pollOnce(projectId: string) {
  await pollProjectOnce(projectId);
  revalidatePath(`/projects/${projectId}`);
}
