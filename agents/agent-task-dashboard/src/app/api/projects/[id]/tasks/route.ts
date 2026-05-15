import { NextResponse } from "next/server";
import { nanoid } from "nanoid";
import { prisma } from "@/lib/prisma";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const tasks = await prisma.task.findMany({ where: { projectId: id }, orderBy: { createdAt: "desc" } });
  return NextResponse.json({ tasks });
}

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.json();
  const task = await prisma.task.create({ data: { projectId: id, taskKey: body.taskKey || `task-${nanoid(8)}`, type: body.type, title: body.title, description: body.description || "", acceptanceCriteria: JSON.stringify(body.acceptanceCriteria ?? [], null, 2), inputJson: JSON.stringify(body.input ?? {}, null, 2) } });
  return NextResponse.json({ task }, { status: 201 });
}
