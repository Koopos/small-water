import Link from "next/link";
import { notFound } from "next/navigation";
import { deleteTask, updateTaskStatus } from "@/app/actions";
import { parseJson } from "@/lib/json";
import { prisma } from "@/lib/prisma";
import { statusClass, statusLabel, taskTypeLabel } from "@/lib/task-types";
import AutoRefresh from "@/components/AutoRefresh";

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="overflow-auto rounded-2xl bg-stone-950 p-4 text-xs leading-6 text-stone-100">{JSON.stringify(value, null, 2)}</pre>;
}

function imageArtifactUrls(value: unknown): string[] {
  if (!value) return [];
  // 支持数组
  if (Array.isArray(value)) {
    return value.flatMap(imageArtifactUrls);
  }
  // 支持对象，遍历所有字段
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap(imageArtifactUrls);
  }
  // 只处理字符串
  if (typeof value !== "string") return [];
  // 检查是否是图片格式
  if (!/\.(png|jpe?g|webp|gif)$/i.test(value)) return [];
  // 本地路径直接返回 /generated/ 格式
  if (value.startsWith("/generated/") || value.startsWith("generated/")) {
    return [value];
  }
  // 已经完整的路径
  if (value.startsWith("http://") || value.startsWith("https://")) {
    return [value];
  }
  return [];
}

function extractImagesFromOutput(output: Record<string, unknown>): string[] {
  // 常见图片字段
  const imageFields = [ "preview_urls"];
  const images: string[] = [];
  for (const field of imageFields) {
    if (output[field]) {
      images.push(...imageArtifactUrls(output[field]));
    }
  }
  // 如果还没找到，遍历整个 output 对象
  if (images.length === 0) {
    images.push(...imageArtifactUrls(output));
  }
  return images;
}

export default async function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const task = await prisma.task.findUnique({ where: { id }, include: { project: true, artifacts: true, runLogs: { orderBy: { startedAt: "desc" } } } });
  if (!task) notFound();

  const retry = updateTaskStatus.bind(null, task.id, "pending");
  const block = updateTaskStatus.bind(null, task.id, "blocked");
  const fail = updateTaskStatus.bind(null, task.id, "failed");
  const removeTask = deleteTask.bind(null, task.id);

  const input = parseJson<Record<string, unknown>>(task.inputJson, {});
  const output = parseJson<Record<string, unknown>>(task.outputJson, {});
  const artifacts = parseJson<unknown[]>(task.artifactsJson, []);

  // 从 output 和 artifacts 中提取图片
  const outputImages = extractImagesFromOutput(output);
  const artifactImages = imageArtifactUrls(artifacts);
  const imageUrls = [...outputImages];

  const showImages = task.status === "completed" && imageUrls.length > 0;

  return (
    <>
      {/* <AutoRefresh projectId={task.projectId} intervalMs={10000} /> */}
      <main className="grid gap-6">
      <section className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
        <Link href={`/projects/${task.projectId}`} className="text-sm font-semibold text-stone-500 hover:text-stone-950">← 返回 {task.project.name}</Link>
        <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(task.status)}`}>{statusLabel(task.status)}</span>
              <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-xs font-semibold text-stone-600">{taskTypeLabel(task.type)}</span>
              <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-xs font-semibold text-stone-600">{task.taskKey}</span>
            </div>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight text-stone-950">{task.title}</h1>
            {task.description && <p className="mt-3 max-w-3xl whitespace-pre-wrap text-stone-700">{task.description}</p>}
          </div>
          <form className="flex flex-wrap gap-2">
            {task.status !== "pending" && <button formAction={retry} className="rounded-full bg-stone-950 px-4 py-2 text-sm font-bold text-white">改回 pending</button>}
            <button formAction={block} className="rounded-full bg-amber-200 px-4 py-2 text-sm font-bold text-stone-950">Block</button>
            <button formAction={fail} className="rounded-full bg-red-100 px-4 py-2 text-sm font-bold text-red-800">Fail</button>
            <button formAction={removeTask} className="rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-bold text-red-700">Delete</button>
          </form>
        </div>
      </section>

      {showImages && (
        <section className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-stone-950">生成的图片</h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {imageUrls.map((url, index) => (
              <a key={url} href={url} target="_blank" className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm hover:border-stone-400">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt={`生成的图片 ${index + 1}`} className="h-auto w-full" />
              </a>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-stone-950">输出</h2>
          <div className="mt-3 grid gap-3 text-stone-700">
            {task.prUrl ? <a href={task.prUrl} target="_blank" className="font-semibold text-blue-700">PR：{task.prUrl}</a> : <p>PR：暂无</p>}
            {task.branch ? <p>Branch：{task.branch}</p> : null}
            {task.error ? <p className="rounded-2xl bg-red-50 p-3 text-red-700">{task.error}</p> : null}
            <JsonBlock value={{ ...output, artifacts }} />
          </div>
        </div>

        <div className="grid gap-6">
          <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-stone-950">时间线</h2>
            <div className="mt-3 grid gap-2 text-sm text-stone-600">
              <p>创建：{task.createdAt.toLocaleString()}</p>
              <p>开始：{task.startedAt?.toLocaleString() ?? "-"}</p>
              <p>完成：{task.completedAt?.toLocaleString() ?? "-"}</p>
              <p>锁：{task.lockedBy ?? "-"} {task.lockedAt?.toLocaleString() ?? ""}</p>
            </div>
          </div>
          <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-stone-950">原始输入</h2>
            <div className="mt-3"><JsonBlock value={input} /></div>
          </div>
        </div>
      </section>
    </main>
    </>
  );
}
