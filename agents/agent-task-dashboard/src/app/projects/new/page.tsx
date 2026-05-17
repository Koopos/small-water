import { createQuickTask } from "@/app/actions";
import CreateTaskForm from "@/app/projects/[id]/CreateTaskForm";

export default function NewProjectPage() {
  return (
    <main className="mx-auto w-full max-w-3xl rounded-[2rem] border border-stone-200 bg-white/85 p-8 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.24em] text-stone-500">New Task</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight text-stone-950">直接添加任务</h1>
      <p className="mt-3 text-stone-600">任务会自动进入默认任务池，并由后端 worker 领取执行；页面会定时刷新状态。</p>

      <CreateTaskForm action={createQuickTask} />
    </main>
  );
}
