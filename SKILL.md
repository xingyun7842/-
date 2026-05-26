---
name: weread-optimizer
description: Use when the user asks for “微信读书优化流程”, wants books/PDFs/MOBI/TXT/images/PPT converted for WeChat Reading/微信读书, or needs EPUBs that preserve body text, heading hierarchy, inline images, and readable layout while removing web/PDF noise. Also use for optional theme classification and quality triage of processed books.
metadata:
  short-description: Convert book folders into WeRead-friendly EPUBs
---

# 微信读书优化流程

## Scope

Process a project folder of source books into a separate output folder for 微信读书:

- primary output: WeRead-friendly EPUB
- optional backup: DOCX only when explicitly useful or requested
- preserve body text, headings, paragraphs, lists, quotes, code blocks, tables, and body images
- keep body images near their original positions; do not dump images at the end
- remove obvious page/web noise:目录页、侧边栏、顶部导航、底部推荐、评论区、按钮、广告、logo、图标、装饰图
- detect video/audio/iframe/mp4/PDF rich media; never silently omit

Use the bundled script for deterministic conversion:

```powershell
& '<bundled-python>' -X utf8 'C:\Users\admin\.codex\skills\weread-optimizer\scripts\weread_optimize.py'
```

Run it with `workdir` set to the user’s book folder. The script processes the current directory unless `WEREAD_INPUT_DIR` is set.

## Required First Steps

1. Count source files and extensions in the current folder.
2. If the user says there should be N numbered files, parse leading numbers and report missing/duplicate/unparseable numbers before finalizing.
3. Check tool/runtime availability. Prefer workspace Python from `load_workspace_dependencies`; install missing packages if needed:
   - `pymupdf`
   - `Pillow`
   - `beautifulsoup4`
   - `mobi`
   - `ebooklib`
4. For PPT/PPTX on Windows, use PowerPoint COM when available to export a temporary PDF, then convert.

## Conversion Script Behavior

`scripts/weread_optimize.py` supports:

- `.pdf`: text/image extraction with PyMuPDF
- `.docx`: paragraphs/headings/tables/inline images to EPUB
- `.mobi`: MOBI unpack to EPUB/HTML/PDF when possible
- `.txt`: original text to EPUB
- `.png/.jpg/.jpeg/.webp`: single-image EPUB with scan note
- `.ppt/.pptx`: PowerPoint export to PDF, then EPUB

Default output structure:

```text
微信读书优化输出/
├── epub/
├── manifest.json
├── 处理报告.md
├── process_stdout.log
└── process_stderr.log
```

Keep temporary working folders only while debugging. Remove `_work_images` and `_converted_pdf` when final outputs are valid.

## Interaction/Rich Media Rule

Before finishing, inspect the report’s “交互组件检查”.

If video/audio/iframe/mp4/RichMedia/Movie/Sound/3D is found:

- state that 微信读书 EPUB cannot fully preserve those interactive components
- state how they were handled: static text/images retained; interaction not embedded; note inserted in the corresponding EPUB
- do not imply full fidelity

## Scan/OCR Limitation Rule

If pages have no text layer:

- preserve them as page images so they can be viewed and enlarged
- mark them as scan/image pages in `处理报告.md`
- clearly state that 微信读书 voice playback cannot fully read those pages
- do not claim complete text extraction unless OCR was actually run

## Validation Checklist

After conversion:

1. Confirm EPUB count vs manifest count.
2. Confirm failures are zero, or list failed files with reasons.
3. Spot-check a few EPUB zip entries and image references if images were extracted.
4. Confirm the report includes:
   - source count
   - missing/duplicate numbered files when applicable
   - rich-media handling
   - scan/image-page handling
   - output list
5. Provide links to:
   - output folder
   - EPUB folder
   - report
   - zip if created

## Optional: Classification and Quality Triage

Only do this when the user asks for classification, reading order,精品/避坑, or thematic organization.

Do not classify only from filenames. Use at least:

- generated EPUB text
- headings/TOC structure
- beginning/middle/end content samples when text is available
- scan-page ratio
- user’s stated interests

Use:

```powershell
& '<bundled-python>' -X utf8 'C:\Users\admin\.codex\skills\weread-optimizer\scripts\extract_toc_samples.py'
```

Then reason over the extracted `微信读书优化输出/目录标题样本.json`.

When creating folders:

- create topic folders under `微信读书优化输出/按主题分类`
- copy each EPUB into exactly one primary topic folder unless the user asks for multi-tag copies
- if creating a 精品 folder, copy精品 EPUBs into `微信读书优化输出/精品书单` in addition to their topic folders

When rating quality, disclose the basis:

- “精品”: high relevance to the user’s stated interests, framework value, practical density, and readable body text or strong scan-material relevance
- “一般推荐”: relevant but narrower, shorter, more dated, mixed quality, or best used as supplement
- “质量太差或不优先”: weak relevance, mostly unrelated stories, empty/low-content files, pure images, very diffuse compilations, or poor fit for the user’s stated goal

If scan-heavy or image-only, say the rating is limited by lack of complete text extraction.

## Final Response Pattern

Keep final concise:

- what was produced
- counts
- any failed/limited files
- links to output artifacts

Do not ask the user to re-upload if the current folder or file library already contains the same files; continue from local files whenever possible.
