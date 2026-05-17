from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .common import pretty_json, safe_text, task_input
from .content import build_image_prompt
from .fs import public_url_for, resolve_artifact_root, write_json, write_placeholder_png, write_text
from .process import run_external_command as _run_external_command


def run_external_command(command: str | list[str], *, cwd: str | None, env: dict[str, str], stdin_text: str):
    from worker import main as worker_main

    if hasattr(worker_main, "run_external_command") and worker_main.run_external_command is not run_external_command:
        return worker_main.run_external_command(command, cwd=cwd, env=env, stdin_text=stdin_text)
    return _run_external_command(command, cwd=cwd, env=env, stdin_text=stdin_text)


def _image_size_for_aspect_ratio(aspect_ratio: str) -> tuple[int, int]:
    ratio = safe_text(aspect_ratio, "square").lower()
    if ratio in {"16:9", "landscape", "wide"}:
        return 1536, 864
    if ratio in {"9:16", "portrait", "vertical"}:
        return 864, 1536
    if ratio in {"3:4", "4:5"}:
        return 1024, 1280
    return 1024, 1024


def _load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    text = safe_text(value, "").strip()
    if not text:
        return fallback
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        return fallback
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _derive_palette(seed: str) -> list[str]:
    digest = __import__("hashlib").sha256(seed.encode("utf-8")).digest()
    base = [digest[0], digest[1], digest[2]]
    accent = [digest[3], digest[4], digest[5]]
    highlight = [digest[6], digest[7], digest[8]]

    def hex_color(rgb: list[int]) -> str:
        return "#%02X%02X%02X" % tuple(rgb)

    return [hex_color(base), hex_color(accent), hex_color(highlight), "#F8FAFC"]


def _interpolate_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(a[0] * (1 - t) + b[0] * t),
        int(a[1] * (1 - t) + b[1] * t),
        int(a[2] * (1 - t) + b[2] * t),
    )


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = safe_text(text, "").strip()
    if not text:
        return []
    lines: list[str] = []
    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            trial = current + char
            width = draw.textbbox((0, 0), trial, font=font)[2]
            if width <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines


def _extract_json_payload(text: str) -> dict[str, Any]:
    raw = safe_text(text, "").strip()
    if not raw:
        return {}

    candidates = [raw]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S | re.I)
    if fenced:
        candidates.insert(0, fenced.group(1))
    first_object = re.search(r"\{.*\}", raw, flags=re.S)
    if first_object:
        candidates.append(first_object.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        return {"result": parsed}
    return {}


def _normalize_plan(
    *,
    task: dict[str, Any],
    prompt: str,
    metadata: dict[str, Any],
    parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parsed or {}
    title = safe_text(parsed.get("title"), safe_text(metadata.get("title"), "图片任务"))
    subtitle = safe_text(parsed.get("subtitle"), safe_text(metadata.get("subject"), safe_text(metadata.get("style"), "")))
    caption = safe_text(parsed.get("caption"), safe_text(metadata.get("copy"), safe_text(task.get("description"), "")))
    palette = parsed.get("palette") if isinstance(parsed.get("palette"), list) else []
    if not palette:
        palette = metadata.get("palette") if isinstance(metadata.get("palette"), list) else []
    if not palette:
        palette = _derive_palette(prompt + pretty_json(metadata))

    elements = parsed.get("elements") if isinstance(parsed.get("elements"), list) else []
    text_blocks = parsed.get("text") if isinstance(parsed.get("text"), list) else []
    background = parsed.get("background") if isinstance(parsed.get("background"), dict) else {}
    layout = parsed.get("layout") if isinstance(parsed.get("layout"), dict) else {}

    return {
        "taskType": task.get("type"),
        "title": title,
        "subtitle": subtitle,
        "caption": caption,
        "palette": palette,
        "background": background or {"type": "gradient", "colors": palette[:2]},
        "layout": layout or {"style": "poster"},
        "elements": elements,
        "text": text_blocks,
        "aspect_ratio": safe_text(metadata.get("aspect_ratio"), "square"),
        "style": safe_text(metadata.get("style"), ""),
        "platform": safe_text(metadata.get("platform"), ""),
        "duration": safe_text(metadata.get("duration"), ""),
        "references": metadata.get("references") if isinstance(metadata.get("references"), list) else [],
        "prompt": prompt,
        "input": metadata.get("input", {}),
        "generated_with_codex": bool(parsed),
    }


def _build_codex_prompt(task: dict[str, Any], prompt: str, metadata: dict[str, Any]) -> str:
    task_json = pretty_json(task)
    metadata_json = pretty_json(metadata)
    return textwrap.dedent(
        f"""
        你是一位资深平面设计师、插画师和海报艺术总监。请根据下面的需求，设计一张可以直接渲染成图片的方案。

        要求：
        1. 只输出严格 JSON，不要输出解释、注释或 Markdown 代码块。
        2. JSON 必须包含以下字段：
           - title: 主标题
           - subtitle: 副标题
           - caption: 辅助文案或角标说明
           - palette: 3~5 个十六进制颜色，例如 ["#0F172A", "#38BDF8"]
           - background: {{"type": "gradient|solid", "colors": ["#..."], "direction": "vertical|horizontal|diagonal"}}
           - layout: {{"style": "poster|banner|cover", "focus": "..."}}
           - text: 一个对象数组，元素需包含 role/text，可选 x/y/align/max_width
           - elements: 一个对象数组，描述装饰元素，可包含 type/color/x/y/size/opacity/label
        3. 文案要根据详细需求生成，不要泛泛而谈。
        4. 如果任务输入中有 subject、scene、mood、lighting、composition、palette、references，请优先遵循。
        5. 如果有中文需求，图中文字必须是中文；避免水印、版权字样和错误拼写。
        6. 设计风格要清晰、可落地、适合后端本地渲染。

        任务自然语言需求：
        {prompt}

        任务输入 JSON：
        {metadata_json}

        完整任务 JSON：
        {task_json}
        """
    ).strip()


def _codex_image_command(prompt: str, output_dir: Path) -> list[str]:
    return ["codex", f"$imagegen {prompt}"]


def _resolve_image_command(prompt: str, output_dir: Path) -> str | list[str]:
    override = os.environ.get("IMAGE_TASK_COMMAND") or os.environ.get("AGENT_IMAGE_COMMAND") or ""
    if override:
        return shlex.split(override) if isinstance(override, str) else override
    return _codex_image_command(prompt, output_dir)


def _generate_plan_with_codex(
    task: dict[str, Any],
    prompt: str,
    metadata: dict[str, Any],
    output_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    codex_prompt = _build_codex_prompt(task, prompt, metadata)
    command = _resolve_image_command(codex_prompt, output_dir)
    env = os.environ.copy()
    env.setdefault("CODEx_ANSI_COLOR", "never")

    result = run_external_command(command, cwd=str(output_dir), env=env, stdin_text="")
    last_message_path = output_dir / "codex-last-message.txt"
    codex_text = ""
    if last_message_path.exists():
        codex_text = last_message_path.read_text(encoding="utf-8").strip()
    if not codex_text:
        codex_text = (result.stdout or "").strip()

    parsed = _extract_json_payload(codex_text) if result.returncode == 0 else {}
    plan = _normalize_plan(task=task, prompt=prompt, metadata=metadata, parsed=parsed)
    run_info = {
        "generated_with_codex": result.returncode == 0 and bool(parsed),
        "codex_returncode": result.returncode,
        "codex_stdout": (result.stdout or "").strip(),
        "codex_stderr": (result.stderr or "").strip(),
        "codex_command": command if isinstance(command, list) else [command],
        "codex_output": codex_text,
    }
    if result.returncode != 0:
        run_info["generated_with_codex"] = False
    return plan, run_info


def _fallback_plan(task: dict[str, Any], prompt: str, metadata: dict[str, Any]) -> dict[str, Any]:
    title = safe_text(metadata.get("title"), safe_text(task.get("title"), "图片任务"))
    description = safe_text(task.get("description"), prompt)
    palette = metadata.get("palette") if isinstance(metadata.get("palette"), list) else []
    if not palette:
        palette = _derive_palette(prompt + pretty_json(metadata))
    return {
        "taskType": task.get("type"),
        "title": title,
        "subtitle": safe_text(metadata.get("style"), safe_text(metadata.get("subject"), "")),
        "caption": description,
        "palette": palette,
        "background": {"type": "gradient", "colors": palette[:2], "direction": "diagonal"},
        "layout": {"style": "poster", "focus": "left text right illustration"},
        "text": [
            {"role": "headline", "text": title, "align": "left", "max_width": 0.55},
            {"role": "subheadline", "text": safe_text(metadata.get("subject"), safe_text(metadata.get("style"), "")), "align": "left", "max_width": 0.5},
            {"role": "footer", "text": description, "align": "left", "max_width": 0.7},
        ],
        "elements": [
            {"type": "circle", "x": 0.78, "y": 0.25, "size": 0.26, "color": palette[1], "opacity": 0.26},
            {"type": "circle", "x": 0.9, "y": 0.18, "size": 0.12, "color": palette[2], "opacity": 0.34},
            {"type": "rectangle", "x": 0.64, "y": 0.62, "size": 0.2, "color": palette[2], "opacity": 0.2},
        ],
        "aspect_ratio": safe_text(metadata.get("aspect_ratio"), "square"),
        "style": safe_text(metadata.get("style"), ""),
        "platform": safe_text(metadata.get("platform"), ""),
        "duration": safe_text(metadata.get("duration"), ""),
        "references": metadata.get("references") if isinstance(metadata.get("references"), list) else [],
        "prompt": prompt,
        "input": metadata.get("input", {}),
        "generated_with_codex": False,
    }


def _draw_element(draw: ImageDraw.ImageDraw, size: tuple[int, int], element: dict[str, Any], palette: list[str]) -> None:
    width, height = size
    color = _hex_to_rgb(safe_text(element.get("color"), palette[0] if palette else "#64748B"), (100, 116, 139))
    opacity = int(float(element.get("opacity", 0.22)) * 255)
    shape_type = safe_text(element.get("type"), "circle").lower()
    x = float(element.get("x", 0.5))
    y = float(element.get("y", 0.5))
    size_factor = float(element.get("size", 0.1))
    radius = max(20, int(min(width, height) * size_factor))
    cx = int(width * x)
    cy = int(height * y)
    fill = (*color, max(0, min(255, opacity)))

    if shape_type in {"circle", "ellipse", "blob"}:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
    elif shape_type in {"rectangle", "card", "block"}:
        draw.rounded_rectangle((cx - radius, cy - radius, cx + radius, cy + radius), radius=max(12, radius // 5), fill=fill)
    elif shape_type in {"line", "bar"}:
        draw.rounded_rectangle((cx - radius, cy - max(4, radius // 6), cx + radius, cy + max(4, radius // 6)), radius=max(4, radius // 6), fill=fill)
    else:
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)

    label = safe_text(element.get("label"), "").strip()[:40]
    if label:
        font_size = max(18, min(42, radius // 3))
        font = _load_font(font_size, bold=True)
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.rounded_rectangle((cx - text_w // 2 - 12, cy - text_h // 2 - 8, cx + text_w // 2 + 12, cy + text_h // 2 + 8), radius=12, fill=(0, 0, 0, 90))
            draw.text((cx - text_w // 2, cy - text_h // 2), label, font=font, fill=(255, 255, 255, 240))
        except Exception:
            pass


def _render_image_plan(plan: dict[str, Any], preview_path: Path, size: tuple[int, int]) -> Path:
    width, height = size
    palette = plan.get("palette") if isinstance(plan.get("palette"), list) else []
    if len(palette) < 3:
        palette = palette + _derive_palette(preview_path.stem)[: max(0, 4 - len(palette))]
    bg_a = _hex_to_rgb(palette[0], (15, 23, 42))
    bg_b = _hex_to_rgb(palette[1], (56, 189, 248))
    bg_c = _hex_to_rgb(palette[2], (244, 114, 182))

    image = Image.new("RGBA", size, bg_a + (255,))
    pixels = image.load()
    for y in range(height):
        t = y / max(1, height - 1)
        row_color = _interpolate_rgb(bg_a, bg_b, t)
        for x in range(width):
            mix = (x / max(1, width - 1) + y / max(1, height - 1)) / 2
            col = _interpolate_rgb(row_color, bg_c, mix * 0.35)
            pixels[x, y] = (*col, 255)

    overlay = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")

    # decorative glows
    for element in plan.get("elements", []) if isinstance(plan.get("elements"), list) else []:
        if isinstance(element, dict):
            _draw_element(draw, size, element, palette)

    # soft framing panel
    panel_left = int(width * 0.06)
    panel_top = int(height * 0.08)
    panel_right = int(width * 0.56)
    panel_bottom = int(height * 0.88)
    draw.rounded_rectangle((panel_left, panel_top, panel_right, panel_bottom), radius=36, fill=(10, 15, 28, 140), outline=(255, 255, 255, 60), width=2)

    # title area
    title = safe_text(plan.get("title"), safe_text(plan.get("input", {}).get("title"), "图片任务"))
    subtitle = safe_text(plan.get("subtitle"), "")
    caption = safe_text(plan.get("caption"), "")
    text_items = plan.get("text") if isinstance(plan.get("text"), list) else []

    title_font = _load_font(max(56, int(width * 0.05)), bold=True)
    subtitle_font = _load_font(max(26, int(width * 0.026)), bold=False)
    body_font = _load_font(max(24, int(width * 0.022)), bold=False)
    small_font = _load_font(max(18, int(width * 0.017)), bold=False)

    text_left = panel_left + 36
    text_top = panel_top + 34
    max_text_width = int(width * 0.44)

    title_lines = _wrap_text(draw, title, title_font, max_text_width)
    y = text_top
    for line in title_lines[:3]:
        draw.text((text_left, y), line, font=title_font, fill=(250, 250, 252, 255))
        y += draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] + 6

    if subtitle:
        y += 8
        for line in _wrap_text(draw, subtitle, subtitle_font, max_text_width)[:4]:
            draw.text((text_left, y), line, font=subtitle_font, fill=(191, 219, 254, 245))
            y += draw.textbbox((0, 0), line, font=subtitle_font)[3] - draw.textbbox((0, 0), line, font=subtitle_font)[1] + 4

    if caption:
        y += 12
        for line in _wrap_text(draw, caption, body_font, max_text_width)[:6]:
            draw.text((text_left, y), line, font=body_font, fill=(226, 232, 240, 240))
            y += draw.textbbox((0, 0), line, font=body_font)[3] - draw.textbbox((0, 0), line, font=body_font)[1] + 4

    # text blocks from plan
    if text_items:
        y += 10
        for item in text_items[:4]:
            if not isinstance(item, dict):
                continue
            role = safe_text(item.get("role"), "text")
            text = safe_text(item.get("text"), "")
            if not text:
                continue
            prefix = {
                "headline": "· ",
                "subheadline": "  ",
                "footer": "  ",
            }.get(role, "  ")
            font = title_font if role == "headline" else subtitle_font if role == "subheadline" else small_font
            lines = _wrap_text(draw, prefix + text, font, max_text_width)
            for line in lines[:4]:
                draw.text((text_left, y), line, font=font, fill=(241, 245, 249, 240))
                y += draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] + 4
            y += 4

    # little footer badge
    badge_text = safe_text(plan.get("layout", {}).get("style"), "poster")
    badge_font = _load_font(18, bold=True)
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = bbox[2] - bbox[0] + 30
    badge_h = bbox[3] - bbox[1] + 18
    badge_x = panel_left + 36
    badge_y = panel_bottom - badge_h - 28
    draw.rounded_rectangle((badge_x, badge_y, badge_x + badge_w, badge_y + badge_h), radius=999, fill=(255, 255, 255, 46), outline=(255, 255, 255, 70), width=1)
    draw.text((badge_x + 15, badge_y + 9), badge_text, font=badge_font, fill=(255, 255, 255, 220))

    # secondary panel on the right for visual balance
    right_panel = (int(width * 0.64), int(height * 0.16), int(width * 0.93), int(height * 0.82))
    draw.rounded_rectangle(right_panel, radius=42, fill=(255, 255, 255, 36), outline=(255, 255, 255, 45), width=2)
    rp_left, rp_top, rp_right, rp_bottom = right_panel
    rp_font = _load_font(max(22, int(width * 0.021)), bold=False)
    rp_title_font = _load_font(max(28, int(width * 0.026)), bold=True)
    rp_title = safe_text(plan.get("layout", {}).get("focus"), safe_text(plan.get("style"), "视觉元素"))
    rp_lines = _wrap_text(draw, rp_title, rp_title_font, rp_right - rp_left - 48)
    cursor_y = rp_top + 34
    for line in rp_lines[:3]:
        draw.text((rp_left + 24, cursor_y), line, font=rp_title_font, fill=(255, 255, 255, 245))
        cursor_y += draw.textbbox((0, 0), line, font=rp_title_font)[3] - draw.textbbox((0, 0), line, font=rp_title_font)[1] + 6

    for line in _wrap_text(draw, pretty_json({"palette": palette[:4], "generated_with_codex": plan.get("generated_with_codex", False)}), rp_font, rp_right - rp_left - 48)[:8]:
        draw.text((rp_left + 24, cursor_y), line, font=rp_font, fill=(226, 232, 240, 240))
        cursor_y += draw.textbbox((0, 0), line, font=rp_font)[3] - draw.textbbox((0, 0), line, font=rp_font)[1] + 5

    image = Image.alpha_composite(image, overlay).convert("RGB")
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(preview_path, format="PNG", optimize=True)
    return preview_path


def _image_files(root: Path) -> list[Path]:
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    return sorted(
        [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in image_exts],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _new_image_files(root: Path, before: set[Path]) -> list[Path]:
    return [path for path in _image_files(root) if path not in before]


def build_image_output(task: dict[str, Any], artifact_root: Path | None = None) -> dict[str, Any]:
    prompt, metadata = build_image_prompt(task)
    root = artifact_root or resolve_artifact_root(task)
    root.mkdir(parents=True, exist_ok=True)
    prompt_path = root / "prompt.txt"
    metadata_path = root / "metadata.json"

    write_text(prompt_path, prompt + "\n")

    before = set(_image_files(root))
    command = _resolve_image_command(prompt, root)
    env = os.environ.copy()
    env.setdefault("CODEX_ANSI_COLOR", "never")
    result = run_external_command(command, cwd=str(root), env=env, stdin_text="")

    generated_images = _new_image_files(root, before)
    used_fallback = False
    if not generated_images:
        used_fallback = True
        preview_path = root / "preview.png"
        write_placeholder_png(preview_path, prompt, _image_size_for_aspect_ratio(safe_text(metadata.get("aspect_ratio"), "square")))
        generated_images = [preview_path]
    else:
        preview_path = generated_images[0]
        if preview_path.name != "preview" + preview_path.suffix:
            preview_copy = root / f"preview{preview_path.suffix.lower()}"
            if preview_path.resolve() != preview_copy.resolve():
                shutil.copyfile(preview_path, preview_copy)
                preview_path = preview_copy
                generated_images.insert(0, preview_path)

    artifacts = [{"type": "image", "path": str(path), "url": public_url_for(path)} for path in generated_images]
    artifacts.append({"type": "prompt", "path": str(prompt_path), "url": public_url_for(prompt_path)})

    metadata_json = {
        **metadata,
        "taskType": task.get("type"),
        "title": safe_text(metadata.get("title"), safe_text(task.get("title"), "图片任务")),
        "prompt": prompt,
        "generated_with_codex": result.returncode == 0 and not used_fallback,
        "codex_returncode": result.returncode,
        "codex_stdout": (result.stdout or "").strip(),
        "codex_stderr": (result.stderr or "").strip(),
        "codex_command": command if isinstance(command, list) else [command],
        "summary": "已直接调用 Codex $imagegen 生成图片。" if not used_fallback else "Codex $imagegen 未生成图片，已写入本地占位图。",
        "preview_urls": [public_url_for(preview_path)],
        "artifacts": artifacts,
    }
    write_json(metadata_path, metadata_json)
    return metadata_json
