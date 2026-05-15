import { NextResponse } from "next/server";
import { syncProjectToGitHub } from "@/lib/github-sync";

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const result = await syncProjectToGitHub(id);
  return NextResponse.json(result, { status: result.ok ? 200 : 500 });
}
