import { NextResponse } from "next/server";
import { completeTask } from "@/lib/task-service";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.json().catch(() => ({}));
  const workerId = String(body.workerId ?? request.headers.get("x-worker-id") ?? "worker");
  const payload = (body.payload ?? body.output ?? {}) as Record<string, unknown>;

  await completeTask(id, workerId, payload);
  return NextResponse.json({ ok: true });
}
