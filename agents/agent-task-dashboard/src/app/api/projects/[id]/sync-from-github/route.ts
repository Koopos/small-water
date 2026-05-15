import { NextResponse } from "next/server";
import { syncProjectFromGitHub } from "@/lib/github-sync";

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const result = await syncProjectFromGitHub(id);
  return NextResponse.json(result, { status: result.ok ? 200 : 500 });
}
