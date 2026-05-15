#!/usr/bin/env python3
"""Generate PNG carousel cards for agent-dating-post task output in dashboard SQLite DB."""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DASHBOARD = Path("/Users/koopos/AIGC/agents/agent-task-dashboard")
DB = DASHBOARD / "dev.db"
AIGC_ROOT = Path("/Users/koopos/AIGC/images/github-file-agent")
PUBLIC_ROOT = DASHBOARD / "public/generated"
W, H = 1080, 1440

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(size: int, index: int = 0) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size, index=index)
    return ImageFont.load_default()


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def wrap_by_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue

        current = ""
        for char in paragraph:
            trial = current + char
            if current and text_width(draw, trial, fnt) > max_width:
                lines.append(current)
                current = char
            else:
                current = trial
        if current:
            lines.append(current)
    return lines


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x: int,
    y: int,
    fnt: ImageFont.ImageFont,
    fill: str,
    line_gap: int,
    paragraph_gap: int,
    align: str = "left",
    max_width: int = 820,
) -> int:
    for line in lines:
        if not line:
            y += paragraph_gap
            continue
        box = draw.textbbox((0, 0), line, font=fnt)
        line_w = box[2] - box[0]
        line_h = box[3] - box[1]
        tx = x + max(0, (max_width - line_w) // 2) if align == "center" else x
        draw.text((tx, y), line, font=fnt, fill=fill)
        y += line_h + line_gap
    return y


def block_height(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    fnt: ImageFont.ImageFont,
    line_gap: int,
    paragraph_gap: int,
) -> int:
    total = 0
    for line in lines:
        if not line:
            total += paragraph_gap
        else:
            box = draw.textbbox((0, 0), line, font=fnt)
            total += box[3] - box[1] + line_gap
    return total


def paper_base(page_num: int) -> Image.Image:
    random.seed(f"codex-dating-card-{page_num}")
    img = Image.new("RGB", (W, H), "#f6eee4")
    px = img.load()
    for y in range(H):
        for x in range(W):
            warm = int(6 * math.sin((x + page_num * 47) / 95) + 4 * math.cos(y / 120))
            grain = random.randint(-5, 5)
            r = 245 + warm + grain - int(y * 0.006)
            g = 235 + int(warm * 0.35) + grain - int(y * 0.004)
            b = 224 + int(warm * 0.18) + grain
            px[x, y] = (
                max(224, min(255, r)),
                max(214, min(247, g)),
                max(204, min(240, b)),
            )

    veil = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(veil)
    vd.rectangle((0, 0, W, H), outline=(105, 71, 59, 24), width=18)
    vd.rectangle((40, 44, W - 40, H - 44), outline=(255, 255, 255, 54), width=2)
    vd.ellipse((-310, 70, 420, 800), fill=(173, 92, 73, 23))
    vd.ellipse((735, 745, 1290, 1445), fill=(145, 114, 91, 24))
    vd.rectangle((112, 206, 124, 1150), fill=(126, 78, 63, 62))
    vd.line((160, 1128, 910, 1128), fill=(118, 82, 66, 54), width=2)
    return Image.alpha_composite(img.convert("RGBA"), veil).filter(ImageFilter.SMOOTH_MORE)


def draw_codex_card(text: str, comment_hook: str, page_num: int, out: Path) -> None:
    img = paper_base(page_num)
    draw = ImageDraw.Draw(img)

    eyebrow = font(30)
    footer = font(26)
    body = font(48 if page_num in {2, 3, 4, 5} else 50)
    title = font(76 if page_num == 1 else 68)
    accent = font(34)

    draw.text((164, 126), "成年人现实恋爱", font=eyebrow, fill="#8b6456")
    page_label = f"0{page_num}/06"
    draw.text((W - 164 - text_width(draw, page_label, eyebrow), 126), page_label, font=eyebrow, fill="#8b6456")

    if page_num == 1:
        lines = wrap_by_width(draw, text, title, 720)
        y = 420
        draw_text_block(draw, lines, 176, y, title, "#241b17", 24, 34, "left", 760)
        draw.rounded_rectangle((164, 930, 525, 998), radius=0, fill=(133, 79, 62, 29))
        draw.text((188, 943), "别把认真聊成用力", font=accent, fill="#805646")
    elif page_num == 6:
        lines = wrap_by_width(draw, text, title, 760)
        y = 470
        draw_text_block(draw, lines, 172, y, title, "#241b17", 24, 34, "left", 780)
        draw.text((164, 1000), "这句话，留给那个让你放松的人。", font=accent, fill="#8a5d4e")
    else:
        lines = wrap_by_width(draw, text, body, 770)
        height = block_height(draw, lines, body, 18, 44)
        y = max(245, (H - height) // 2 - 10)
        draw_text_block(draw, lines, 172, y, body, "#2d2420", 18, 44, "left", 780)

    footer_text = "舒服的聊天，不需要每句话都证明自己"
    if page_num == 5:
        footer_text = "没有回应的热情，最后都会变成自我怀疑"
    if page_num == 6:
        footer_text = comment_hook or "你同意吗？"
    footer_lines = wrap_by_width(draw, footer_text, footer, 760)
    draw_text_block(draw, footer_lines, 164, 1180, footer, "#8a6a5d", 12, 20, "left", 780)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)


def draw_legacy_card(text: str, page_num: int, out: Path) -> None:
    img = Image.new("RGB", (W, H), "#f8efe7")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((90, 110, 990, 1330), radius=56, fill=(255, 255, 255, 172))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    fnt = font(52 if page_num != 1 else 72)
    lines = wrap_by_width(draw, text, fnt, 780)
    y = max(260, (H - block_height(draw, lines, fnt, 16, 38)) // 2)
    draw_text_block(draw, lines, 150, y, fnt, "#2d2421", 16, 38, "center", 780)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)


def normalize_pages(pages: object) -> dict[str, str]:
    if isinstance(pages, list):
        return {f"page_{i + 1}": str(value) for i, value in enumerate(pages)}
    if isinstance(pages, dict):
        return {str(key): str(value) for key, value in pages.items()}
    return {}


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_key", nargs="?", help="Task key. Defaults to latest agent-dating-post task.")
    parser.add_argument(
        "--codex-style",
        action="store_true",
        default=True,
        help="Generate restrained Codex-designed Xiaohongshu/Douyin cards. This is the default.",
    )
    parser.add_argument("--legacy-style", action="store_true", help="Use the old simple centered-card layout.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    if args.task_key:
        row = con.execute("select * from Task where taskKey=?", (args.task_key,)).fetchone()
    else:
        row = con.execute(
            "select * from Task where type='agent-dating-post' order by createdAt desc limit 1"
        ).fetchone()
    if not row:
        raise SystemExit("No agent-dating-post task found")

    output = json.loads(row["outputJson"] or "{}")
    pages = normalize_pages(output.get("pages") or {})
    if not pages:
        raise SystemExit("Task has no pages in outputJson")

    task_key = row["taskKey"]
    codex_style = not args.legacy_style
    prefix = "codex-page" if codex_style else "page"
    image_dir = AIGC_ROOT / task_key
    public_dir = PUBLIC_ROOT / task_key
    comment_hook = str(output.get("comment_hook") or "")
    abs_paths: list[str] = []
    public_urls: list[str] = []

    for i in range(1, 7):
        text = pages.get(f"page_{i}", "")
        img_path = image_dir / f"{prefix}-{i}.png"
        public_path = public_dir / f"{prefix}-{i}.png"
        if codex_style:
            draw_codex_card(text, comment_hook, i, img_path)
        else:
            draw_legacy_card(text, i, img_path)
        public_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(img_path, public_path)
        abs_paths.append(str(img_path))
        public_urls.append(f"/generated/{task_key}/{prefix}-{i}.png")

    old_artifacts = [str(item) for item in output.get("artifacts") or []]
    merged = unique([*old_artifacts, *abs_paths, *public_urls])
    output["artifacts"] = merged
    output["image_artifacts"] = abs_paths
    output["preview_urls"] = public_urls
    output["image_style"] = "codex-xhs-restrained" if codex_style else "legacy-centered"
    summary = output.get("summary") or "已生成相亲图文文案"
    output["summary"] = summary.split(" 已补充生成 6 张")[0] + " 已补充生成 6 张 Codex 设计图文卡片 PNG。"

    con.execute(
        "update Task set outputJson=?, artifactsJson=?, updatedAt=CURRENT_TIMESTAMP where id=?",
        (
            json.dumps(output, ensure_ascii=False, indent=2),
            json.dumps(merged, ensure_ascii=False, indent=2),
            row["id"],
        ),
    )
    con.commit()
    print(
        json.dumps(
            {"taskKey": task_key, "image_dir": str(image_dir), "public_urls": public_urls},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
