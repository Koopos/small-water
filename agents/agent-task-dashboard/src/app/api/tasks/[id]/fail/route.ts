import { NextResponse } from "next/server";
import { failTask } from "@/lib/task-service";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const body = await request.json().catch(() => ({}));
  const workerId = String(body.workerId ?? request.headers.get("x-worker-id") ?? "worker");
  const error = String(body.error ?? body.message ?? "Worker failed");
  const payload = (body.payload ?? {}) as Record<string, unknown>;

  await failTask(id, workerId, error, payload);
  return NextResponse.json({ ok: true });
}
