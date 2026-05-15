import { readFile } from "fs/promises";
import { join } from "path";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const imagePath = searchParams.get("path");

  if (!imagePath) {
    return NextResponse.json({ error: "Missing path parameter" }, { status: 400 });
  }

  // 安全检查：只允许 images 或 generated 目录
  const allowedPatterns = ["/images/", "/generated/", "images/", "generated/"];
  const isAllowed = allowedPatterns.some((pattern) =>
    imagePath.includes(pattern)
  );
  if (!isAllowed) {
    return NextResponse.json({ error: "Invalid path" }, { status: 403 });
  }

  let fullPath: string | undefined;
  try {
    // 构建完整路径 - 使用 AIGC 目录
    const baseDir = process.env.AIGC_BASE_DIR ?? process.env.HOME ?? "/tmp";
    const normalizedPath = imagePath.startsWith("/")
      ? imagePath.replace(/^\//, "")
      : imagePath;
    fullPath = join(baseDir, normalizedPath);

    const imageBuffer = await readFile(fullPath);

    // 根据扩展名判断 content-type
    const ext = imagePath.split(".").pop()?.toLowerCase() ?? "";
    const contentTypes: Record<string, string> = {
      png: "image/png",
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      webp: "image/webp",
      gif: "image/gif",
    };
    const contentType = contentTypes[ext] ?? "application/octet-stream";

    return new NextResponse(imageBuffer, {
      headers: { "Content-Type": contentType },
    });
  } catch (error) {
    console.error("Failed to read image:", error);
    console.error("Attempted path:", fullPath);
    return NextResponse.json({ error: "Image not found", path: fullPath ?? imagePath }, { status: 404 });
  }
}
