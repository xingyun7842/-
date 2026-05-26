from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import shutil
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    import fitz
except Exception:
    fitz = None

try:
    from PIL import Image
except Exception:
    Image = None

ROOT = Path(os.environ.get("WEREAD_INPUT_DIR", Path.cwd())).resolve()
OUT = Path(os.environ.get("WEREAD_OUTPUT_DIR", ROOT / "微信读书优化输出")).resolve()
EPUB_DIR = OUT / "epub"
IMG_TMP = OUT / "_work_images"
REPORT = OUT / "处理报告.md"
MANIFEST = OUT / "manifest.json"
SOURCE_EXTS = {".html", ".htm", ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
HTML_EXTS = {".html", ".htm"}

NOISE_SELECTORS = "script,style,noscript,svg,canvas,iframe,video,audio,button,form,header,footer,nav,aside"
NOISE_CLASSES = ["advert", "ads", "share", "comment", "comments", "sidebar", "recommend", "footer", "header"]
INTERACTIVE_RE = re.compile(r"<\s*(video|audio|iframe)\b|\.mp4\b", re.I)


def safe_name(value: str, max_len: int = 96) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    if not value:
        value = "untitled"
    if len(value) > max_len:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
        value = value[: max_len - 9].rstrip() + "_" + digest
    return value


def source_sort_key(path: Path) -> tuple[int, int, str]:
    m = re.match(r"^\s*(\d{1,4})(?=\D|$)", path.name)
    if m:
        return (0, int(m.group(1)), path.name.lower())
    return (1, 10**9, path.name.lower())


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def iter_sources() -> list[Path]:
    html_only = os.environ.get("WEREAD_HTML_ONLY", "").lower() in {"1", "true", "yes"}
    sources = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name.startswith("~$"):
            continue
        if path.suffix.lower() not in SOURCE_EXTS:
            continue
        if html_only and path.suffix.lower() not in HTML_EXTS:
            continue
        if is_under(path, OUT):
            continue
        sources.append(path)
    return sorted(sources, key=source_sort_key)


def output_stem(source: Path) -> str:
    rel = source.relative_to(ROOT)
    base = source.stem if len(rel.parts) == 1 else "__".join(rel.with_suffix("").parts)
    m = re.match(r"^\s*(\d{1,4})(?=\D|$)", source.name)
    if m:
        return safe_name(f"{int(m.group(1)):02d}-{base}")
    return safe_name(base)


def xhtml_doc(title: str, body: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN">\n'
        f'<head><title>{html.escape(title)}</title><meta charset="utf-8" />'
        '<link rel="stylesheet" type="text/css" href="../styles.css" /></head>\n'
        f"<body>\n{body}\n</body>\n</html>\n"
    )


def media_type(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}.get(ext, "application/octet-stream")


def write_epub(epub_path: Path, title: str, chapters: list[tuple[str, str]], images: list[tuple[Path, str]]) -> None:
    uid = hashlib.sha1((title + str(time.time())).encode("utf-8")).hexdigest()
    css = """
body{font-family:serif;line-height:1.78;margin:0 4%;color:#111}h1,h2,h3{line-height:1.35;text-indent:0;break-after:avoid;page-break-after:avoid}h1{font-size:1.45em;text-align:center;margin:1.2em 0 1em}h1.chapter-title{border-bottom:1px solid #ddd;padding-bottom:.55em}h2{font-size:1.25em;margin:1.35em 0 .7em}h3{font-size:1.08em;margin:1.05em 0 .45em}p{margin:.58em 0;text-indent:2em}p.noindent,.note,.scan-note{ text-indent:0 }ul,ol{margin:.55em 0 .55em 1.45em;padding:0}li{margin:.25em 0;line-height:1.65}blockquote{margin:.8em 0 .8em .4em;padding-left:.8em;border-left:.18em solid #999;color:#444;text-indent:0}pre{white-space:pre-wrap;overflow-wrap:break-word;font-family:monospace;font-size:.88em;line-height:1.45;margin:.85em 0;padding:.65em;background:#f6f6f6;text-indent:0}table{border-collapse:collapse;width:100%;margin:1em 0}td,th{border:1px solid #999;padding:.35em .45em;vertical-align:top;text-indent:0}th{font-weight:700;background:#f2f2f2}.compare-table td{width:50%;font-size:.92em}.table-card{border:1px solid #bbb;margin:.75em 0;padding:.45em .65em}.table-card p{text-indent:0;margin:.32em 0}img{max-width:100%;height:auto;display:block;margin:.9em auto}.note,.scan-note{color:#666;font-size:.9em}
"""
    manifest = ['<item id="nav" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>', '<item id="css" href="styles.css" media-type="text/css"/>']
    spine = []
    nav_items = []
    chapter_files = []
    for index, (chapter_title, body) in enumerate(chapters, 1):
        href = f"text/part{index:04d}.xhtml"
        item_id = f"part{index:04d}"
        chapter_files.append((href, xhtml_doc(chapter_title, body)))
        manifest.append(f'<item id="{item_id}" href="{href}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{item_id}"/>')
        nav_items.append(f'<li><a href="{href}">{html.escape(chapter_title)}</a></li>')
    for index, (_, arcname) in enumerate(images, 1):
        manifest.append(f'<item id="img{index:05d}" href="{arcname}" media-type="{media_type(arcname)}"/>')
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:uuid:{uid}</dc:identifier><dc:title>{html.escape(title)}</dc:title><dc:language>zh-CN</dc:language></metadata><manifest>{''.join(manifest)}</manifest><spine>{''.join(spine)}</spine></package>'''
    nav = xhtml_doc("目录", '<nav epub:type="toc" id="toc"><h1>目录</h1><ol>' + "".join(nav_items) + "</ol></nav>")
    container = '<?xml version="1.0" encoding="UTF-8"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    epub_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.xhtml", nav)
        zf.writestr("OEBPS/styles.css", css)
        for href, content in chapter_files:
            zf.writestr("OEBPS/" + href, content)
        for source, arcname in images:
            zf.write(source, "OEBPS/" + arcname)


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", "replace")


def save_data_image(src: str, img_dir: Path, stem: str, index: int) -> tuple[Path, str] | None:
    if not src.startswith("data:image/"):
        return None
    m = re.match(r"data:image/([a-zA-Z0-9.+-]+);base64,(.*)", src, re.S)
    if not m:
        return None
    ext = m.group(1).lower().split("+", 1)[0].replace("jpeg", "jpg")
    try:
        data = base64.b64decode(m.group(2), validate=False)
    except Exception:
        return None
    img_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_name(f"{stem}_{index:04d}.{ext}", 120)
    out = img_dir / filename
    out.write_bytes(data)
    return out, f"images/{filename}"


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([，。！？：；、）】》”’])", r"\1", text)
    return text


def html_cell(cell) -> str:
    text = clean_text(cell.get_text(" ", strip=True))
    return html.escape(text)


def convert_table(node) -> str:
    cells = node.select(".table_cell") or node.find_all(["td", "th"])
    if not cells:
        return ""
    cols = 2
    for cls in node.get("class", []):
        m = re.fullmatch(r"table_(\d+)", str(cls))
        if m:
            cols = max(1, int(m.group(1)))
    rows = []
    for start in range(0, len(cells), cols):
        values = [html_cell(c) for c in cells[start:start+cols]]
        if any(values):
            tag = "th" if not rows else "td"
            rows.append("<tr>" + "".join(f"<{tag}>{v}</{tag}>" for v in values) + "</tr>")
    return '<table class="data-table">' + "".join(rows) + "</table>" if rows else ""


def convert_grid(node, img_dir: Path, stem: str, image_index: int) -> tuple[str, list[tuple[Path, str]], int]:
    images = []
    cols = node.select(".grid_column") or node.find_all(recursive=False)
    cells = []
    for col in cols:
        parts = []
        for img in col.find_all("img"):
            saved = save_data_image(img.get("src", ""), img_dir, stem, image_index + 1)
            if saved:
                image_index += 1
                images.append(saved)
                parts.append(f'<img src="../{html.escape(saved[1])}" alt="图 {image_index}" />')
        text = clean_text(col.get_text(" ", strip=True))
        if text:
            parts.append(html.escape(text))
        if parts:
            cells.append("<br/>".join(parts))
    if len(cells) >= 2:
        return '<table class="compare-table"><tr>' + "".join(f"<td>{c}</td>" for c in cells) + "</tr></table>", images, image_index
    return "".join(f'<p class="noindent">{c}</p>' for c in cells), images, image_index


def extract_html(source: Path) -> tuple[str, str, list[tuple[Path, str]], list[str]]:
    text = read_text(source)
    interactive = ["HTML interactive/media"] if INTERACTIVE_RE.search(text) else []
    if BeautifulSoup is None:
        return source.stem, f"<pre>{html.escape(text)}</pre>", [], interactive
    soup = BeautifulSoup(text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title and soup.title.get_text(strip=True) else source.stem
    for tag in soup.select(NOISE_SELECTORS):
        tag.decompose()
    for cls in NOISE_CLASSES:
        for tag in soup.select(f".{cls}"):
            tag.decompose()
    img_dir = IMG_TMP / safe_name(source.stem)
    images = []
    blocks = []
    image_index = 0
    items = soup.select(".vc-doc-item, .table, .grid, table, blockquote, pre") or [(soup.body or soup)]
    for item in items:
        classes = item.get("class", []) if hasattr(item, "get") else []
        if item.name == "table" or "table" in classes:
            table_html = convert_table(item)
            if table_html:
                blocks.append(table_html)
            continue
        if "grid" in classes:
            grid_html, grid_images, image_index = convert_grid(item, img_dir, safe_name(source.stem), image_index)
            blocks.append(grid_html)
            images.extend(grid_images)
            continue
        if item.name == "blockquote" or "quote_container" in classes or "vc-quote_container" in classes:
            quote = clean_text(item.get_text(" ", strip=True))
            if quote:
                blocks.append(f"<blockquote>{html.escape(quote)}</blockquote>")
            continue
        if item.name == "pre" or item.find("pre"):
            code = (item.find("pre") or item).get_text("\n").strip()
            if code:
                blocks.append(f"<pre>{html.escape(code)}</pre>")
            continue
        for img in item.find_all("img"):
            saved = save_data_image(img.get("src", ""), img_dir, safe_name(source.stem), image_index + 1)
            if saved:
                image_index += 1
                images.append(saved)
                blocks.append(f'<p class="noindent"><img src="../{html.escape(saved[1])}" alt="图 {image_index}" /></p>')
        text_value = clean_text(item.get_text(" ", strip=True))
        if not text_value or text_value in {"•", "-", "—"}:
            continue
        if item.find(["h1", "h2"]):
            blocks.append(f"<h2>{html.escape(text_value)}</h2>")
        elif item.find(["h3", "h4"]):
            blocks.append(f"<h3>{html.escape(text_value)}</h3>")
        elif re.fullmatch(r"https?://\S+", text_value):
            blocks.append(f'<p class="noindent"><a href="{html.escape(text_value, quote=True)}">{html.escape(text_value)}</a></p>')
        else:
            blocks.append(f"<p>{html.escape(text_value)}</p>")
    if interactive:
        blocks.insert(0, '<p class="note">[提示] 检测到 video/audio/iframe/mp4 等交互或媒体标记。微信读书 EPUB 不能完整嵌入交互媒体；本次保留可抽取正文与静态图片。</p>')
    return title, "\n".join(blocks) or f"<p>{html.escape(clean_text((soup.body or soup).get_text(' ', strip=True)))}</p>", images, interactive


def chapter_title(source: Path, fallback: str) -> str:
    title = re.sub(r"\s+", " ", source.stem.replace("_", "/")).strip()
    m = re.match(r"^\s*(\d{1,4})(?=\D|$)", title)
    if m:
        title = f"{int(m.group(1)):02d} {title}"
    return title or fallback or source.stem


def convert_html(source: Path, out_epub: Path) -> dict:
    title, body, images, interactive = extract_html(source)
    title = chapter_title(source, title)
    body = f'<h1 class="chapter-title">{html.escape(title)}</h1>\n' + body
    write_epub(out_epub, title, [(title, body)], images)
    return result(source, out_epub, pages=1, images=len(images), interactive=interactive)


def convert_html_collection(sources: list[Path], out_epub: Path, title: str) -> dict:
    chapters = []
    images = []
    interactive = []
    for source in sources:
        fallback, body, img_entries, hits = extract_html(source)
        ctitle = chapter_title(source, fallback)
        chapters.append((ctitle, f'<h1 class="chapter-title">{html.escape(ctitle)}</h1>\n{body}'))
        images.extend(img_entries)
        interactive.extend([f"{source.name}: {hit}" for hit in hits])
    write_epub(out_epub, title, chapters, images)
    return result(ROOT, out_epub, pages=len(chapters), images=len(images), interactive=interactive, sources=[str(p) for p in sources])


def text_body(text: str, title: str) -> str:
    blocks = [f'<h1 class="chapter-title">{html.escape(title)}</h1>']
    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    for para in paragraphs:
        value = clean_text(para)
        if not value:
            continue
        if len(value) <= 70 and re.match(r"^(第.+[章节篇回]|[一二三四五六七八九十]+[、.．]|[0-9]{1,3}[、.．]|【.+】)", value):
            blocks.append(f"<h2>{html.escape(value)}</h2>")
        else:
            blocks.append(f"<p>{html.escape(value)}</p>")
    return "\n".join(blocks)


def convert_txt(source: Path, out_epub: Path) -> dict:
    title = chapter_title(source, source.stem)
    write_epub(out_epub, title, [(title, text_body(read_text(source), title))], [])
    return result(source, out_epub, pages=1)


def convert_image(source: Path, out_epub: Path) -> dict:
    img_dir = IMG_TMP / safe_name(source.stem)
    img_dir.mkdir(parents=True, exist_ok=True)
    dest = img_dir / safe_name(source.name, 120)
    shutil.copy2(source, dest)
    arc = "images/" + dest.name
    size = "unknown"
    if Image is not None:
        try:
            with Image.open(source) as im:
                size = f"{im.width}x{im.height}"
        except Exception:
            pass
    title = chapter_title(source, source.stem)
    body = f'<h1 class="chapter-title">{html.escape(title)}</h1><p class="scan-note">[源文件是图片，已保留为整页图片；可查看和放大，但微信读书语音朗读无法读取图片中的文字。尺寸：{html.escape(size)}]</p><img src="../{html.escape(arc)}" alt="{html.escape(title)}" />'
    write_epub(out_epub, title, [(title, body)], [(dest, arc)])
    return result(source, out_epub, pages=1, images=1, scan_pages=1, warnings=["源文件是图片，无文本层"])


def convert_pdf(source: Path, out_epub: Path) -> dict:
    if fitz is None:
        raise RuntimeError("缺少 pymupdf，无法转换 PDF")
    doc = fitz.open(str(source))
    img_dir = IMG_TMP / safe_name(source.stem)
    img_dir.mkdir(parents=True, exist_ok=True)
    chapters = []
    images = []
    scan_pages = 0
    for page_index, page in enumerate(doc, 1):
        text = clean_text(page.get_text("text"))
        if text:
            body = "\n".join(f"<p>{html.escape(p)}</p>" for p in re.split(r"(?<=[。！？])\s+", text) if p.strip())
        else:
            scan_pages += 1
            pix = page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False)
            filename = f"{safe_name(source.stem, 40)}_p{page_index:04d}.jpg"
            img_path = img_dir / filename
            pix.save(str(img_path), jpg_quality=82)
            arc = "images/" + filename
            images.append((img_path, arc))
            body = f'<p class="scan-note">[扫描页 {page_index}：没有可抽取文本层，已按整页图片保留。]</p><img src="../{html.escape(arc)}" alt="扫描页 {page_index}" />'
        if page_index == 1:
            body = f'<h1 class="chapter-title">{html.escape(source.stem)}</h1>\n' + body
        if page_index % 80 == 1:
            chapters.append((f"{source.stem} - 第 {len(chapters)+1} 部分", body))
        else:
            title, old = chapters[-1]
            chapters[-1] = (title, old + "\n" + body)
    write_epub(out_epub, source.stem, chapters or [(source.stem, f"<p>{html.escape(source.stem)}</p>")], images)
    return result(source, out_epub, pages=doc.page_count, images=len(images), scan_pages=scan_pages)


def result(source: Path, epub: Path, pages: int = 0, images: int = 0, scan_pages: int = 0, interactive: list[str] | None = None, warnings: list[str] | None = None, sources: list[str] | None = None) -> dict:
    row = {"source": str(source), "epub": str(epub), "status": "ok", "pages": pages, "images_kept": images, "images_removed": 0, "scan_pages": scan_pages, "interactive": interactive or [], "warnings": warnings or []}
    if sources:
        row["sources"] = sources
    return row


def write_report(sources: list[Path], rows: list[dict], elapsed: float) -> None:
    ok = [r for r in rows if r.get("status") == "ok"]
    failed = [r for r in rows if r.get("status") != "ok"]
    numbered: dict[int, list[str]] = defaultdict(list)
    for path in sources:
        m = re.match(r"^\s*(\d{1,4})(?=\D|$)", path.name)
        if m:
            numbered[int(m.group(1))].append(path.name)
    max_number = max(numbered) if numbered else 0
    missing = [str(i) for i in range(1, max_number + 1) if i not in numbered] if max_number else []
    duplicates = {k: v for k, v in numbered.items() if len(v) > 1}
    lines = ["# 微信读书优化处理报告", "", f"- 源目录：`{ROOT}`", f"- 输出目录：`{OUT}`", f"- 源文件数：{len(sources)}", f"- 成功生成 EPUB：{len(ok)}", f"- 失败：{len(failed)}", f"- 保留图片：{sum(r.get('images_kept', 0) for r in ok)}", f"- 扫描/图片页：{sum(r.get('scan_pages', 0) for r in ok)}", f"- 用时：{elapsed/60:.1f} 分钟", "", "## 编号检查", "", f"- 缺少序号：{', '.join(missing) if missing else '无'}"]
    if duplicates:
        lines.append("- 重复序号：" + "；".join(f"{k}: {', '.join(v)}" for k, v in sorted(duplicates.items())))
    interactive = [r for r in ok if r.get("interactive")]
    lines += ["", "## 交互组件检查", ""]
    if interactive:
        lines.append("检测到交互/媒体标记；EPUB 已保留正文与静态图片，交互媒体未嵌入。")
        for row in interactive:
            lines.append(f"- {Path(row['source']).name}：{', '.join(row.get('interactive', []))}")
    else:
        lines.append("未检测到 video/audio/iframe/mp4 等交互媒体标记。")
    if failed:
        lines += ["", "## 失败文件", ""]
        for row in failed:
            lines.append(f"- {Path(row['source']).name}：{row.get('error')}")
    lines += ["", "## 输出清单", ""]
    for row in rows:
        if row.get("status") == "ok":
            lines.append(f"- `{Path(row['epub']).name}` ← `{Path(row['source']).name}`")
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    EPUB_DIR.mkdir(parents=True, exist_ok=True)
    IMG_TMP.mkdir(parents=True, exist_ok=True)
    sources = iter_sources()
    rows = []
    start = time.time()
    if os.environ.get("WEREAD_COMBINE_HTML", "").lower() in {"1", "true", "yes"}:
        html_sources = [p for p in sources if p.suffix.lower() in HTML_EXTS]
        title = os.environ.get("WEREAD_COLLECTION_TITLE", ROOT.name or "合集")
        rows.append(convert_html_collection(html_sources, EPUB_DIR / f"{safe_name(title)}.epub", title))
    else:
        counts = Counter(output_stem(p) for p in sources)
        for source in sources:
            stem = output_stem(source)
            if counts[stem] > 1:
                stem = safe_name(f"{stem}__{source.suffix.lower().lstrip('.')}")
            out_epub = EPUB_DIR / f"{stem}.epub"
            try:
                ext = source.suffix.lower()
                if ext in HTML_EXTS:
                    row = convert_html(source, out_epub)
                elif ext == ".txt":
                    row = convert_txt(source, out_epub)
                elif ext == ".pdf":
                    row = convert_pdf(source, out_epub)
                elif ext in {".png", ".jpg", ".jpeg", ".webp"}:
                    row = convert_image(source, out_epub)
                else:
                    raise RuntimeError(f"暂不支持的文件类型：{ext}")
            except Exception as exc:
                row = {"source": str(source), "epub": str(out_epub), "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            rows.append(row)
            MANIFEST.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(sources, rows, time.time() - start)
    print(f"Done. EPUB: {EPUB_DIR}")
    print(f"Report: {REPORT}")
    return 0 if all(r.get("status") == "ok" for r in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
