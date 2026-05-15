import { mkdir, readFile, writeFile } from "fs/promises";
import { dirname, join } from "path";
import { execFile } from "child_process";
import { promisify } from "util";
import { prisma } from "@/lib/prisma";
import { parseJson } from "@/lib/json";

const execFileAsync = promisify(execFile);
const DEFAULT_WORKROOT = `${process.env.HOME ?? "/tmp"}/AIGC/agents/github-task-agent/repos`;

interface SyncResult {
  ok: boolean;
  message: string;
  stdout?: string;
  stderr?: string;
}

function assertSafeRepoPart(value: string, label: string) {
  if (!/^[A-Za-z0-9_.-]+$/.test(value)) {
    throw new Error(`${label} 只能包含字母、数字、下划线、点和短横线`);
  }
}

async function run(command: string, args: string[], cwd?: string) {
  const result = await execFileAsync(command, args, { cwd, maxBuffer: 1024 * 1024 * 10 });
  return `${result.stdout ?? ""}${result.stderr ?? ""}`.trim();
}

export async function ensureRepo(projectId: string) {
  const project = await prisma.project.findUniqueOrThrow({ where: { id: projectId } });
  assertSafeRepoPart(project.owner, "owner");
  assertSafeRepoPart(project.repo, "repo");

  const repoFullName = `${project.owner}/${project.repo}`;
  const localPath = project.localPath || join(DEFAULT_WORKROOT, `${project.owner}__${project.repo}`);

  await mkdir(DEFAULT_WORKROOT, { recursive: true });

  try {
    await run("git", ["-C", localPath, "status"]);
  } catch {
    await run("gh", ["repo", "clone", repoFullName, localPath]);
  }

  await run("git", ["fetch", "origin", "--prune"], localPath);
  await run("git", ["checkout", project.defaultBranch], localPath);
  await run("git", ["pull", "--ff-only", "origin", project.defaultBranch], localPath);

  if (!project.localPath) {
    await prisma.project.update({ where: { id: project.id }, data: { localPath } });
  }

  return { project: { ...project, localPath }, localPath, repoFullName };
}

export async function syncProjectToGitHub(projectId: string): Promise<SyncResult> {
  const { project, localPath } = await ensureRepo(projectId);
  const tasks = await prisma.task.findMany({ where: { projectId }, orderBy: { createdAt: "asc" } });

  const payload = {
    version: 1,
    updated_at: new Date().toISOString(),
    tasks: tasks.map((task) => ({
      id: task.taskKey,
      type: task.type,
      status: task.status,
      priority: task.priority,
      title: task.title,
      description: task.description,
      acceptance_criteria: parseJson<string[]>(task.acceptanceCriteria, []),
      input: parseJson<Record<string, unknown>>(task.inputJson, {}),
      output: {
        ...parseJson<Record<string, unknown>>(task.outputJson, {}),
        branch: task.branch,
        pr_url: task.prUrl,
        artifacts: parseJson<unknown[]>(task.artifactsJson, []),
      },
      error: task.error,
      created_at: task.createdAt.toISOString(),
      started_at: task.startedAt?.toISOString() ?? null,
      completed_at: task.completedAt?.toISOString() ?? null,
      locked_by: task.lockedBy,
      locked_at: task.lockedAt?.toISOString() ?? null,
    })),
  };

  const filePath = join(localPath, project.taskFilePath);
  await mkdir(dirname(filePath), { recursive: true });
  await writeFile(filePath, JSON.stringify(payload, null, 2) + "\n", "utf8");

  await run("git", ["add", project.taskFilePath], localPath);

  const status = await run("git", ["status", "--porcelain", project.taskFilePath], localPath);
  if (!status) {
    await prisma.project.update({ where: { id: projectId }, data: { lastSyncedAt: new Date() } });
    return { ok: true, message: "没有变化，GitHub 已是最新" };
  }

  await run("git", ["commit", "-m", "chore(agent): sync task queue"], localPath);
  const stdout = await run("git", ["push", "origin", project.defaultBranch], localPath);
  await prisma.project.update({ where: { id: projectId }, data: { lastSyncedAt: new Date() } });
  return { ok: true, message: "已同步到 GitHub", stdout };
}

export async function syncProjectFromGitHub(projectId: string): Promise<SyncResult> {
  const { project, localPath } = await ensureRepo(projectId);
  const filePath = join(localPath, project.taskFilePath);
  const raw = await readFile(filePath, "utf8");
  const data = JSON.parse(raw) as { tasks?: Array<Record<string, unknown>> };

  for (const item of data.tasks ?? []) {
    const taskKey = String(item.id ?? "");
    if (!taskKey) continue;
    const output = (item.output ?? {}) as Record<string, unknown>;
    await prisma.task.upsert({
      where: { projectId_taskKey: { projectId, taskKey } },
      create: {
        projectId,
        taskKey,
        type: String(item.type ?? "agent-task"),
        status: String(item.status ?? "pending"),
        priority: String(item.priority ?? "normal"),
        title: String(item.title ?? taskKey),
        description: String(item.description ?? ""),
        acceptanceCriteria: JSON.stringify(item.acceptance_criteria ?? [], null, 2),
        inputJson: JSON.stringify(item.input ?? {}, null, 2),
        outputJson: JSON.stringify(output, null, 2),
        error: item.error ? String(item.error) : null,
        branch: output.branch ? String(output.branch) : null,
        prUrl: output.pr_url ? String(output.pr_url) : null,
        artifactsJson: JSON.stringify(output.artifacts ?? [], null, 2),
      },
      update: {
        type: String(item.type ?? "agent-task"),
        status: String(item.status ?? "pending"),
        priority: String(item.priority ?? "normal"),
        title: String(item.title ?? taskKey),
        description: String(item.description ?? ""),
        acceptanceCriteria: JSON.stringify(item.acceptance_criteria ?? [], null, 2),
        inputJson: JSON.stringify(item.input ?? {}, null, 2),
        outputJson: JSON.stringify(output, null, 2),
        error: item.error ? String(item.error) : null,
        branch: output.branch ? String(output.branch) : null,
        prUrl: output.pr_url ? String(output.pr_url) : null,
        artifactsJson: JSON.stringify(output.artifacts ?? [], null, 2),
      },
    });
  }

  await prisma.project.update({ where: { id: projectId }, data: { lastSyncedAt: new Date() } });
  return { ok: true, message: `已从 GitHub 同步 ${data.tasks?.length ?? 0} 个任务` };
}

export async function pollProjectOnce(projectId: string): Promise<SyncResult> {
  const { project, localPath, repoFullName } = await ensureRepo(projectId);
  const script = `${process.env.HOME}/AIGC/agents/github-task-agent/scripts/poll-github-task-agent.sh`;
  const startedAt = new Date();
  try {
    const stdout = await run(script, [repoFullName, project.taskFilePath]);
    await prisma.runLog.create({
      data: { projectId, runId: `poll-${startedAt.getTime()}`, status: "completed", stdout, completedAt: new Date() },
    });
    return { ok: true, message: "Poll once 已执行", stdout };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await prisma.runLog.create({
      data: { projectId, runId: `poll-${startedAt.getTime()}`, status: "failed", stderr: message, completedAt: new Date() },
    });
    return { ok: false, message, stderr: message };
  } finally {
    void localPath;
  }
}
