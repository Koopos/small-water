from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import pretty_json, safe_text, task_artifacts, task_input
from .fs import public_url_for, resolve_artifact_root, write_json, write_placeholder_png, write_text

def make_content_pages(title: str, description: str) -> list[dict[str, str]]:
    hook = title or "标题待补"
    lead = description or hook
    return [
        {"page": "1", "headline": hook, "body": f"用一句扎心的话切入：{lead}", "visual": "强情绪封面，黑底白字"},
        {"page": "2", "headline": "问题不是没消息，而是没选择", "body": "把对方的沉默解释成答案，而不是谜题。", "visual": "聊天气泡+留白"},
        {"page": "3", "headline": "真正忙的人会告诉你忙", "body": "长期失联，往往说明优先级不在你这里。", "visual": "日历与消息通知"},
        {"page": "4", "headline": "别拿你的认真换别人的敷衍", "body": "识别投入不对等，及时止损。", "visual": "天平/失衡构图"},
        {"page": "5", "headline": "把力气留给愿意回应的人", "body": "关系里最重要的是反馈，不是幻想。", "visual": "向前走的背影"},
        {"page": "6", "headline": "结尾金句", "body": "成年人最体面的告别，是读懂沉默。", "visual": "大字收尾页"},
    ]

def build_dating_post_output(task: dict[str, Any], task_input_data: dict[str, Any]) -> dict[str, Any]:
    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), "相亲图文"))
    description = safe_text(task.get("description"))
    pages = make_content_pages(title, description)
    return {
        "taskType": task.get("type"),
        "title": title,
        "summary": f"已生成 {len(pages)} 页相亲图文结构，适合直接拆成多图发布。",
        "style": "情绪化 / 扎心 / 口语化",
        "pages": pages,
        "hashtags": ["#情感", "#成年人", "#相亲", "#关系"],
        "prompt": description,
        "input": task_input_data,
    }

def build_article_output(task: dict[str, Any], task_input_data: dict[str, Any]) -> dict[str, Any]:
    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), "图文文章"))
    description = safe_text(task.get("description"))
    outline = [
        "引子：用一个具体场景进入",
        "背景：交代问题和受众",
        "观点：给出核心判断",
        "展开：分三点论证",
        "收尾：行动建议与总结",
    ]
    body = [
        f"{title}。",
        "先从一个真实场景切入，让读者迅速进入语境。",
        "再把问题拆成背景、冲突和解决方案。",
        "最后给出明确建议，方便直接发布。",
    ]
    return {
        "taskType": task.get("type"),
        "title": title,
        "summary": f"已生成文章骨架，包含 {len(outline)} 段大纲。",
        "outline": outline,
        "body": body,
        "seo": {"keywords": [title, "图文", "内容创作"]},
        "prompt": description,
        "input": task_input_data,
    }

def build_hot_content_output(task: dict[str, Any], task_input_data: dict[str, Any]) -> dict[str, Any]:
    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), "热点图文"))
    description = safe_text(task.get("description"))
    return {
        "taskType": task.get("type"),
        "title": title,
        "summary": "已整理热点角度、事实核实与发布建议。",
        "angle": ["热点事件中的共性问题", "普通人最容易忽视的细节", "情绪背后的现实选择"],
        "fact_check": ["确认来源", "区分事实与观点", "避免夸大结论"],
        "publish_notes": ["标题尽量短", "正文先给结论", "配图突出情绪点"],
        "prompt": description,
        "input": task_input_data,
    }

def build_video_script_output(task: dict[str, Any], task_input_data: dict[str, Any]) -> dict[str, Any]:
    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), "视频脚本"))
    description = safe_text(task.get("description"))
    scenes = [
        {"scene": 1, "shot": "开场钩子", "line": f"{title}，先抛出最扎心的一句。"},
        {"scene": 2, "shot": "问题展开", "line": "用一个具体例子解释冲突。"},
        {"scene": 3, "shot": "观点总结", "line": "给出明确判断和下一步建议。"},
    ]
    return {
        "taskType": task.get("type"),
        "title": title,
        "summary": "已生成三段式口播脚本与分镜。",
        "hook": f"{title}，到底说明了什么？",
        "scenes": scenes,
        "narration": [scene["line"] for scene in scenes],
        "prompt": description,
        "input": task_input_data,
    }

def build_content_output(task: dict[str, Any]) -> dict[str, Any]:
    task_input_data = task_input(task)
    task_type = safe_text(task.get("type"), "agent-task")
    if task_type == "agent-dating-post":
        return build_dating_post_output(task, task_input_data)
    if task_type == "agent-article":
        return build_article_output(task, task_input_data)
    if task_type == "agent-hot-content":
        return build_hot_content_output(task, task_input_data)
    if task_type == "agent-video-script":
        return build_video_script_output(task, task_input_data)

    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), task_type))
    return {
        "taskType": task_type,
        "title": title,
        "summary": "已生成通用任务摘要。",
        "description": safe_text(task.get("description")),
        "input": task_input_data,
    }

def build_image_prompt(task: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    task_input_data = task_input(task)
    title = safe_text(task.get("title"), safe_text(task.get("taskKey"), "图片任务"))
    description = safe_text(task.get("description"))
    style = safe_text(task_input_data.get("style"), "")
    platform = safe_text(task_input_data.get("platform"), "")
    duration = safe_text(task_input_data.get("duration"), "")
    aspect_ratio = safe_text(task_input_data.get("aspect_ratio"), "square")
    subject = safe_text(task_input_data.get("subject"), "")
    scene = safe_text(task_input_data.get("scene"), "")
    mood = safe_text(task_input_data.get("mood"), "")
    lighting = safe_text(task_input_data.get("lighting"), "")
    palette = task_input_data.get("palette") if isinstance(task_input_data.get("palette"), list) else []
    composition = safe_text(task_input_data.get("composition"), "")
    copy = safe_text(task_input_data.get("copy"), "")
    negative_prompt = safe_text(task_input_data.get("negative_prompt"), "")
    references = task_input_data.get("references") if isinstance(task_input_data.get("references"), list) else []

    prompt_parts = [
        f"标题: {title}",
        f"需求: {description}",
    ]
    for label, value in (
        ("subject", subject),
        ("scene", scene),
        ("style", style),
        ("mood", mood),
        ("lighting", lighting),
        ("composition", composition),
        ("copy", copy),
        ("negative_prompt", negative_prompt),
        ("platform", platform),
        ("duration", duration),
        ("aspect_ratio", aspect_ratio),
    ):
        if value:
            prompt_parts.append(f"{label}: {value}")
    if palette:
        prompt_parts.append("palette: " + ", ".join(str(item) for item in palette))
    if references:
        prompt_parts.append("references: " + "; ".join(str(item) for item in references))

    metadata = {
        "taskType": task.get("type"),
        "title": title,
        "aspect_ratio": aspect_ratio,
        "style": style,
        "platform": platform,
        "duration": duration,
        "subject": subject,
        "scene": scene,
        "mood": mood,
        "lighting": lighting,
        "palette": palette,
        "composition": composition,
        "copy": copy,
        "negative_prompt": negative_prompt,
        "references": references,
        "input": task_input_data,
    }
    return "\n".join(part for part in prompt_parts if part), metadata

def build_content_task_output(task: dict[str, Any]) -> dict[str, Any]:
    output = build_content_output(task)
    artifact_root = resolve_artifact_root(task)
    write_json(artifact_root / "output.json", output)
    return output
