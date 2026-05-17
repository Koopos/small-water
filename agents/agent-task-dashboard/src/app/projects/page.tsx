import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { statusClass, statusLabel } from "@/lib/task-types";

export const dynamic = "force-dynamic";

export default async function ProjectsPage() {
  const projects = await prisma.project.findMany({
    orderBy: { updatedAt: "desc" },
    include: { tasks: true },
  });

  return (
    <main className="grid gap-6">
      <section className="rounded-[2rem] border border-stone-200 bg-stone-950 p-8 text-white shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-amber-200">任务池 + Worker 模式</p>
        <div className="mt-5 grid gap-6 lg:grid-cols-[1.4fr_0.6fr] lg:items-end">
          <div>
            <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">直接添加任务，后端 worker 负责领取执行。</h1>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-stone-300">
              任务状态、租约、重试和执行结果都落在 PostgreSQL；页面会定时刷新后端数据，不再依赖 GitHub 项目或任务文件。
            </p>
          </div>
          <Link href="/projects/new" className="justify-self-start rounded-full bg-amber-200 px-5 py-3 text-sm font-bold text-stone-950 hover:bg-amber-100 lg:justify-self-end">
            直接添加任务
          </Link>
        </div>
      </section>

      <section className="grid gap-4">
        {projects.length === 0 ? (
          <div className="rounded-[2rem] border border-dashed border-stone-300 bg-white/70 p-10 text-center">
            <h2 className="text-2xl font-semibold text-stone-950">还没有任务池</h2>
            <p className="mt-2 text-stone-600">先添加一个任务，系统会自动创建默认任务池并进入队列。</p>
          </div>
        ) : (
          projects.map((project) => {
            const counts = project.tasks.reduce<Record<string, number>>((acc, task) => {
              acc[task.status] = (acc[task.status] ?? 0) + 1;
              return acc;
            }, {});
            return (
              <Link key={project.id} href={`/projects/${project.id}`} className="group rounded-[2rem] border border-stone-200 bg-white/80 p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-sm font-medium text-stone-500">本地任务池</p>
                    <h2 className="mt-1 text-2xl font-semibold tracking-tight text-stone-950 group-hover:text-stone-700">{project.name}</h2>
                    <p className="mt-2 text-sm text-stone-500">任务总数：{project.tasks.length} · 最近更新：{project.updatedAt.toLocaleString()}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {["pending", "running", "blocked", "failed", "completed"].map((status) => (
                      <span key={status} className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusClass(status)}`}>
                        {statusLabel(status)} {counts[status] ?? 0}
                      </span>
                    ))}
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </section>
    </main>
  );
}
