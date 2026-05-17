import { NextResponse } from "next/server";
import { claimNextTask } from "@/lib/task-service";
import type { WorkerPool } from "@/lib/task-routing";

export async function POST(request: Request, context: { params: Promise<{ pool: string }> }) {
  const { pool } = await context.params;
  if (!["code", "image", "content"].includes(pool)) {
    return NextResponse.json({ ok: false, error: "Invalid worker pool" }, { status: 400 });
  }

  const body = await request.json().catch(() => ({}));
  const workerId = String(body.workerId ?? request.headers.get("x-worker-id") ?? "worker");
  const result = await claimNextTask(pool as WorkerPool, workerId);

  if (!result) {
    return NextResponse.json({ ok: true, task: null });
  }

  return NextResponse.json({ ok: true, task: result.task, claim: result.claim });
}
