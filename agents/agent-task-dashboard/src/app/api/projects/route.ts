import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const projects = await prisma.project.findMany({ orderBy: { updatedAt: "desc" }, include: { _count: { select: { tasks: true } } } });
  return NextResponse.json({ projects });
}

export async function POST(request: Request) {
  const body = await request.json();
  const [owner, repo] = String(body.fullName ?? "").split("/");
  if (!owner || !repo) return NextResponse.json({ error: "fullName must be owner/repo" }, { status: 400 });
  const project = await prisma.project.create({ data: { name: body.name || repo, owner, repo, defaultBranch: body.defaultBranch || "main", taskFilePath: body.taskFilePath || ".agent/tasks.json" } });
  return NextResponse.json({ project }, { status: 201 });
}
