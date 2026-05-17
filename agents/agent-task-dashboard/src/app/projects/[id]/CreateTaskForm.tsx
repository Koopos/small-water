"use client";

import { useState } from "react";
import { TASK_TYPES } from "@/lib/task-types";

interface CreateTaskFormProps {
  action: (formData: FormData) => void;
}

const SIMPLE_TASK_TYPES = ["agent-dev", "agent-image", "agent-dating-post"] as const;

export default function CreateTaskForm({ action }: CreateTaskFormProps) {
  const [type, setType] = useState<string>("agent-dating-post");

  const showDescription = type === "agent-dev" || type === "agent-image";
  const showRepoName = type === "agent-dev";

  const selectedType = TASK_TYPES.find((t) => t.value === type);

  const getHint = () => {
    if (type === "agent-dating-post") return "只需选择类型，填写标题和优先级即可";
    if (type === "agent-dev") return "需要填写关联仓库或参考信息、详细需求，其他字段可选";
    if (type === "agent-image") return "需要填写详细需求，其他字段可选";
    return selectedType?.hint ?? "";
  };

  return (
    <form action={action} className="mt-5 grid gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">任务类型</span>
          <select
            name="type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-2xl border border-stone-200 bg-white px-4 py-3"
          >
            {TASK_TYPES.filter((t) => SIMPLE_TASK_TYPES.includes(t.value as typeof SIMPLE_TASK_TYPES[number])).map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
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
        <input
          name="title"
          required
          placeholder={type === "agent-dating-post" ? "例如：成年人突然不联系，其实就是答案" : "输入任务标题"}
          className="rounded-2xl border border-stone-200 bg-white px-4 py-3"
        />
      </label>

      {showRepoName && (
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">关联仓库 / 参考信息</span>
          <input
            name="repoName"
            required
            placeholder="例如：本地仓库路径、repo 名、参考链接"
            className="rounded-2xl border border-stone-200 bg-white px-4 py-3"
          />
        </label>
      )}

      {showDescription && (
        <label className="grid gap-2">
          <span className="text-sm font-semibold text-stone-700">详细需求</span>
          <textarea
            name="description"
            required
            rows={5}
            placeholder={type === "agent-dev" ? "写清楚目标、背景、限制和输出要求" : "描述图片需求：主题、风格、场景等"}
            className="rounded-2xl border border-stone-200 bg-white px-4 py-3"
          />
        </label>
      )}

      <p className="text-sm text-stone-500">{getHint()}</p>

      <button type="submit" className="rounded-full bg-stone-950 px-5 py-3 font-bold text-white hover:bg-stone-800">
        创建 pending 任务
      </button>
    </form>
  );
}
