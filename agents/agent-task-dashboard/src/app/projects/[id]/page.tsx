import Link from "next/link";
import { notFound } from "next/navigation";
import { createTask, pollOnce, syncFromGitHub, syncToGitHub } from "@/app/actions";
import { prisma } from "@/lib/prisma";
import { STATUSES, TASK_TYPES, statusClass, statusLabel, taskTypeLabel } from "@/lib/task-types";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const project = await prisma.project.findUnique({
    where: { id },
    include: { tasks: { orderBy: { createdAt: "desc" } }, runLogs: { orderBy: { startedAt: "desc" }, take: 5 } },
  });
  if (!project) notFound();

  const createTaskForProject = createTask.bind(null, project.id);
  const syncToGitHubForProject = syncToGitHub.bind(null, project.id);
  const syncFromGitHubForProject = syncFromGitHub.bind(null, project.id);
  const pollOnceForProject = pollOnce.bind(null, project.id);

  return (
    <main className="grid gap-6">
      <section className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-stone-500">{project.owner}/{project.repo}</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-stone-950">{project.name}</h1>
            <p className="mt-3 text-stone-600">任务文件：{project.taskFilePath} · 默认分支：{project.defaultBranch}</p>
            <p className="mt-1 text-sm text-stone-500">本地路径：{project.localPath ?? "首次同步时自动 clone"}</p>
          </div>
          <form className="flex flex-wrap gap-2">
            <button formAction={syncToGitHubForProject} className="rounded-full bg-stone-950 px-4 py-2 text-sm font-bold text-white">Sync to GitHub</button>
            <button formAction={syncFromGitHubForProject} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-bold text-stone-800">Sync from GitHub</button>
            <button formAction={pollOnceForProject} className="rounded-full bg-amber-200 px-4 py-2 text-sm font-bold text-stone-950">Poll once</button>
          </form>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.95fr_1.5fr]">
        <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
          <h2 className="text-2xl font-semibold tracking-tight text-stone-950">创建任务</h2>
          <p className="mt-2 text-sm text-stone-600">相亲图文任务只需要选择“相亲图文”，填写标题和优先级；详细需求、验收标准和其它字段都可以不填。</p>
          <form action={createTaskForProject} className="mt-5 grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-stone-700">任务类型</span>
                <select name="type" className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  {TASK_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}
                </select>
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-semibold text-stone-700">优先级</span>
                <select name="priority" className="rounded-2xl border border-stone-200 bg-white px-4 py-3">
                  <option value="normal">normal</option>
                  <option value="high">high</option>
                  <option value="low">low</option>
                </select>
              </label>
            </div>
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">标题</span>
              <input name="title" required placeholder="例如：成年人突然不联系，其实就是答案" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">详细需求（相亲图文可不填）</span>
              <textarea name="description" rows={5} placeholder="写清楚目标、背景、限制和输出要求" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <label className="grid gap-2">
              <span className="text-sm font-semibold text-stone-700">验收标准（一行一个，相亲图文可不填）</span>
              <textarea name="acceptanceCriteria" rows={4} className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <input name="style" placeholder="风格，如：科技感、干净" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
              <input name="platform" placeholder="平台，如：小红书/抖音" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
              <input name="duration" placeholder="时长，如：60s" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
              <input name="aspectRatio" placeholder="比例，如：landscape" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            </div>
            <textarea name="references" rows={3} placeholder="参考链接/素材路径，一行一个" className="rounded-2xl border border-stone-200 bg-white px-4 py-3" />
            <label className="flex items-center gap-2 text-sm font-medium text-stone-700"><input type="checkbox" name="requireScreenshot" /> 前端/视觉任务需要效果截图</label>
            <button className="rounded-full bg-stone-950 px-5 py-3 font-bold text-white hover:bg-stone-800">创建 pending 任务</button>
          </form>
        </div>

        <div className="grid gap-4">
          <h2 className="text-2xl font-semibold tracking-tight text-stone-950">任务看板</h2>
          <div className="grid gap-4 xl:grid-cols-5">
            {STATUSES.map((status) => {
              const tasks = project.tasks.filter((task) => task.status === status);
              return (
                <div key={status} className="rounded-[1.5rem] border border-stone-200 bg-white/70 p-3">
                  <div className={`mb-3 inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(status)}`}>{statusLabel(status)} · {tasks.length}</div>
                  <div className="grid gap-2">
                    {tasks.map((task) => (
                      <Link key={task.id} href={`/tasks/${task.id}`} className="rounded-2xl border border-stone-200 bg-white p-3 text-sm shadow-sm hover:border-stone-400">
                        <span className="text-xs font-semibold text-stone-500">{task.taskKey} · {taskTypeLabel(task.type)}</span>
                        <span className="mt-1 block font-semibold text-stone-950">{task.title}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="rounded-[1.5rem] border border-stone-200 bg-white/75 p-4">
            <h3 className="font-semibold text-stone-950">最近运行日志</h3>
            <div className="mt-3 grid gap-2 text-sm text-stone-600">
              {project.runLogs.length === 0 ? <p>暂无日志</p> : project.runLogs.map((log) => <p key={log.id}>{log.status} · {log.startedAt.toLocaleString()}</p>)}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
