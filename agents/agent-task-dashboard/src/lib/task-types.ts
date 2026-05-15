export const TASK_TYPES = [
  { value: "agent-dev", label: "代码开发", tone: "emerald", hint: "熟悉代码、制定计划、实现、测试、截图、PR" },
  { value: "agent-image", label: "生图", tone: "amber", hint: "生成图片资产、保存 prompt 和产物路径" },
  { value: "agent-video-script", label: "视频脚本", tone: "sky", hint: "标题、口播稿、分镜表、封面文案" },
  { value: "agent-article", label: "图文文章", tone: "lime", hint: "标题、正文、摘要、配图建议" },
  { value: "agent-hot-content", label: "热点图文", tone: "rose", hint: "热点角度、事实核实、发布建议" },
  { value: "agent-dating-post", label: "相亲图文", tone: "pink", hint: "只需标题和优先级；按爆款情感图文结构生成多页内容" },
] as const;

export const STATUSES = ["pending", "running", "blocked", "failed", "completed"] as const;

export type TaskStatus = (typeof STATUSES)[number];

export function statusLabel(status: string) {
  const labels: Record<string, string> = {
    pending: "等待",
    running: "运行中",
    blocked: "阻塞",
    failed: "失败",
    completed: "完成",
  };
  return labels[status] ?? status;
}

export function statusClass(status: string) {
  const classes: Record<string, string> = {
    pending: "bg-stone-100 text-stone-700 border-stone-200",
    running: "bg-blue-100 text-blue-800 border-blue-200",
    blocked: "bg-amber-100 text-amber-800 border-amber-200",
    failed: "bg-red-100 text-red-800 border-red-200",
    completed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  };
  return classes[status] ?? classes.pending;
}

export function taskTypeLabel(type: string) {
  return TASK_TYPES.find((item) => item.value === type)?.label ?? type;
}
