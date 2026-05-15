import { createProject } from "@/app/actions";

export default function NewProjectPage() {
  return (
    <main className="mx-auto w-full max-w-3xl rounded-[2rem] border border-stone-200 bg-white/85 p-8 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.24em] text-stone-500">New Project</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight text-stone-950">接入一个 GitHub 仓库</h1>
      <p className="mt-3 text-stone-600">系统会通过 gh CLI clone/pull 仓库，并维护 .agent/tasks.json。</p>

      <form action={createProject} className="mt-8 grid gap-5">
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">显示名称</span>
          <input name="name" placeholder="Baby App Agent" className="rounded-2xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-stone-500" />
        </label>
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">GitHub 仓库 owner/repo</span>
          <input name="fullName" required placeholder="Koopos/my-repo" className="rounded-2xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-stone-500" />
        </label>
        <div className="grid gap-5 sm:grid-cols-2">
          <label className="grid gap-2">
            <span className="text-sm font-semibold text-stone-700">默认分支</span>
            <input name="defaultBranch" defaultValue="main" className="rounded-2xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-stone-500" />
          </label>
          <label className="grid gap-2">
            <span className="text-sm font-semibold text-stone-700">轮询间隔（分钟）</span>
            <input name="pollIntervalMinutes" defaultValue="15" className="rounded-2xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-stone-500" />
          </label>
        </div>
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">任务文件路径</span>
          <input name="taskFilePath" defaultValue=".agent/tasks.json" className="rounded-2xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-stone-500" />
        </label>
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">本地路径（可选）</span>
          <input name="localPath" placeholder="默认：~/AIGC/agents/github-task-agent/repos/owner__repo" className="rounded-2xl border border-stone-200 bg-white px-4 py-3 outline-none focus:border-stone-500" />
        </label>
        <button className="rounded-full bg-stone-950 px-5 py-3 font-bold text-white hover:bg-stone-800">创建项目</button>
      </form>
    </main>
  );
}
