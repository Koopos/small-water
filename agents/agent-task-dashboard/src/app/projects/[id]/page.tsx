import Link from "next/link";
import { notFound } from "next/navigation";
import { createTask } from "@/app/actions";
import { prisma } from "@/lib/prisma";
import { STATUSES, statusClass, statusLabel, taskTypeLabel } from "@/lib/task-types";
import CreateTaskForm from "./CreateTaskForm";
import AutoRefresh from "@/components/AutoRefresh";

export const dynamic = "force-dynamic";

export default async function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const project = await prisma.project.findUnique({
    where: { id },
    include: { tasks: { orderBy: { createdAt: "desc" } }, runLogs: { orderBy: { startedAt: "desc" }, take: 5 } },
  });
  if (!project) notFound();

  const createTaskForProject = createTask.bind(null, project.id);

  return (
    <main className="grid gap-6">
      <section className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-stone-500">本地任务池</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-stone-950">{project.name}</h1>
            <p className="mt-3 text-stone-600">这里显示当前任务池中的任务，页面会定时拉取后端最新状态。</p>
            <p className="mt-1 text-sm text-stone-500">最近更新：{project.updatedAt.toLocaleString()}</p>
          </div>
          <AutoRefresh endpointPath={`/api/projects/${id}`} intervalMs={10000} />
          <div className="flex flex-wrap gap-2">
            <Link href="/projects/new" className="rounded-full bg-stone-950 px-4 py-2 text-sm font-bold text-white">新建任务</Link>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-[0.95fr_1.5fr]">
        <div className="rounded-[2rem] border border-stone-200 bg-white/85 p-6 shadow-sm">
          <h2 className="text-2xl font-semibold tracking-tight text-stone-950">创建任务</h2>
          <CreateTaskForm action={createTaskForProject} />
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
                        <span className="text-xs font-semibold text-stone-500">{task.taskKey} · {taskTypeLabel(task.type)} · {task.workerPool ?? "content"}</span>
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
