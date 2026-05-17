import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { createTaskRecord } from "@/lib/task-service";
import { getWorkerPoolForType } from "@/lib/task-routing";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const tasks = await prisma.task.findMany({ where: { projectId: id }, orderBy: { createdAt: "desc" } });
  return NextResponse.json({ tasks });
}

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.json();
  const task = await createTaskRecord({
    projectId: id,
    taskKey: body.taskKey || `task-${crypto.randomUUID().slice(0, 8)}`,
    type: String(body.type ?? "agent-task"),
    workerPool: getWorkerPoolForType(String(body.type ?? "agent-task")),
    priority: String(body.priority ?? "normal"),
    title: String(body.title ?? "Untitled task"),
    description: String(body.description ?? ""),
    acceptanceCriteria: JSON.stringify(body.acceptanceCriteria ?? [], null, 2),
    inputJson: JSON.stringify(body.input ?? {}, null, 2),
    outputJson: JSON.stringify(body.output ?? {}, null, 2),
    artifactsJson: JSON.stringify(body.artifacts ?? [], null, 2),
  });
  return NextResponse.json({ task }, { status: 201 });
}
