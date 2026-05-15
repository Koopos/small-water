import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import { deleteTask, updateTask, updateTaskStatus } from "@/app/actions";
import { parseJson } from "@/lib/json";
import { prisma } from "@/lib/prisma";
import { STATUSES, TASK_TYPES, statusClass, statusLabel, taskTypeLabel } from "@/lib/task-types";

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="overflow-auto rounded-2xl bg-stone-950 p-4 text-xs leading-6 text-stone-100">{JSON.stringify(value, null, 2)}</pre>;
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function referencesValue(value: unknown) {
  return Array.isArray(value) ? value.map(String).join("\n") : "";
}

function imageArtifactUrls(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value
    .map(String)
    .filter((item) => /\.(png|jpe?g|webp|gif)$/i.test(item))
    .filter((item) => item.startsWith("/generated/") || item.startsWith("http://") || item.startsWith("https://"));
}

export default async function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const task = await prisma.task.findUnique({ where: { id }, include: { project: true, artifacts: true, runLogs: { orderBy: { startedAt: "desc" } } } });
  if (!task) notFound();

  const retry = updateTaskStatus.bind(null, task.id, "pending");
  const block = updateTaskStatus.bind(null, task.id, "blocked");
  const fail = updateTaskStatus.bind(null, task.id, "failed");
  const saveTask = updateTask.bind(null, task.id);
  const removeTask = deleteTask.bind(null, task.id);
  const criteria = parseJson<string[]>(task.acceptanceCriteria, []);
  const input = parseJson<Record<string, unknown>>(task.inputJson, {});
  const output = parseJson<Record<string, unknown>>(task.outputJson, {});
  const artifacts = parseJson<unknown[]>(task.artifactsJson, []);
  const imageUrls = imageArtifactUrls(output.preview_urls ?? artifacts);

  return (
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
            <p className="mt-3 max-w-3xl whitespace-pre-wrap text-stone-700">{task.description || "未填写详细需求"}</p>
          </div>
          <form className="flex flex-wrap gap-2">
            <button formAction={retry} className="rounded-full bg-stone-950 px-4 py-2 text-sm font-bold text-white">改回 pending</button>
            <button formAction={block} className="rounded-full bg-amber-200 px-4 py-2 text-sm font-bold text-stone-950">Block</button>
            <button formAction={fail} className="rounded-full bg-red-100 px-4 py-2 text-sm font-bold text-red-800">Fail</button>
            <button formAction={removeTask} className="rounded-full border border-red-200 bg-white px-4 py-2 text-sm font-bold text-red-700">Delete</button>
          </form>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
          <h2 className="text-xl font-semibold text-stone-950">编辑任务</h2>
          <p className="mt-2 text-sm text-stone-600">Blocked 任务可以在这里补充需求，然后把状态改回 pending，再 Sync to GitHub / Poll once。相亲图文任务只需要标题和优先级，其它字段可以留空。</p>
          <form action={saveTask} className="mt-5 grid gap-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-stone-700">状态</span>
                <select name="status" defaultValue={task.status} className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  {STATUSES.map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}
                </select>
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-stone-700">类型</span>
                <select name="type" defaultValue={task.type} className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  {TASK_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-stone-700">优先级</span>
                <select name="priority" defaultValue={task.priority} className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  <option value="high">high</option>
                  <option value="normal">normal</option>
                  <option value="low">low</option>
                </select>
              </label>
            </div>
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">标题</span>
              <input name="title" required defaultValue={task.title} className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">详细需求（相亲图文可不填）</span>
              <textarea name="description" rows={6} defaultValue={task.description} className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">验收标准（一行一个，相亲图文可不填）</span>
              <textarea name="acceptanceCriteria" rows={4} defaultValue={criteria.join("\n")} className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <input name="style" defaultValue={stringValue(input.style)} placeholder="风格" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
              <input name="platform" defaultValue={stringValue(input.platform)} placeholder="平台" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
              <input name="duration" defaultValue={stringValue(input.duration)} placeholder="时长" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
              <input name="aspectRatio" defaultValue={stringValue(input.aspect_ratio)} placeholder="比例，如 landscape" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </div>
            <textarea name="references" rows={3} defaultValue={referencesValue(input.references)} placeholder="参考链接/素材路径，一行一个" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">错误/阻塞原因</span>
              <textarea name="error" rows={3} defaultValue={task.error ?? ""} className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <label className="flex items-center gap-2 text-sm font-medium text-stone-700"><input type="checkbox" name="requireScreenshot" defaultChecked={input.require_screenshot === true} /> 前端/视觉任务需要效果截图</label>
            <button className="rounded-full bg-stone-950 px-5 py-3 font-bold text-white hover:bg-stone-800">保存修改</button>
          </form>
        </div>

        <div className="grid gap-6">
          <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
            <h2 className="text-xl font-semibold text-stone-950">输出</h2>
            <div className="mt-3 grid gap-3 text-stone-700">
              {task.prUrl ? <a href={task.prUrl} target="_blank" className="font-semibold text-blue-700">PR：{task.prUrl}</a> : <p>PR：暂无</p>}
              {task.branch ? <p>Branch：{task.branch}</p> : null}
              {task.error ? <p className="rounded-2xl bg-red-50 p-3 text-red-700">{task.error}</p> : null}
              {imageUrls.length > 0 ? (
                <div className="grid gap-3 sm:grid-cols-2">
                  {imageUrls.map((url, index) => (
                    <a key={url} href={url} target="_blank" className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
                      <Image src={url} alt={`图文卡片 ${index + 1}`} width={1080} height={1440} className="h-auto w-full" />
                    </a>
                  ))}
                </div>
              ) : null}
              <JsonBlock value={{ ...output, artifacts }} />
            </div>
          </div>
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
            <div className="mt-3"><JsonBlock value={{ criteria, input }} /></div>
          </div>
        </div>
      </section>
    </main>
  );
}
