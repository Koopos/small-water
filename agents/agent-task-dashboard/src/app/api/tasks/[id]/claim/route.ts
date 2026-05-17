import { NextResponse } from "next/server";
import { claimNextTask } from "@/lib/task-service";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.json().catch(() => ({}));
  const workerId = String(body.workerId ?? request.headers.get("x-worker-id") ?? "worker");
  const pool = String(body.pool ?? request.headers.get("x-worker-pool") ?? "content") as "code" | "image" | "content";

  if (body.taskId && String(body.taskId) !== id) {
    return NextResponse.json({ ok: false, error: "Task id mismatch" }, { status: 400 });
  }

  const result = await claimNextTask(pool, workerId);
  if (!result) {
    return NextResponse.json({ ok: true, task: null });
  }

  return NextResponse.json({ ok: true, task: result.task, claim: result.claim });
}
