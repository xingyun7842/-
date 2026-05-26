# weread-optimizer

Codex skill for converting course/book folders into WeRead-friendly EPUB files.

## What It Does

- Converts HTML, PDF, DOCX, TXT, MOBI, images, and PPT/PPTX into EPUB.
- Optimizes HTML exports for WeRead by extracting readable content blocks instead of dumping full webpages.
- Preserves headings, paragraphs, lists, code blocks, links, tables, comparison grids, blockquotes, and body images.
- Converts div-based pseudo tables and comparison grids into EPUB-friendly tables.
- Removes common web noise such as scripts, navigation, buttons, comments, sidebars, and next-chapter cards.
- Keeps interactive media notes for video/audio/iframe content because EPUB cannot embed those interactions reliably.

## Install

Clone or download this repository into your Codex skills directory:

### Windows PowerShell

```powershell
$SkillDir = "$env:USERPROFILE\.codex\skills\weread-optimizer"
New-Item -ItemType Directory -Force -Path (Split-Path $SkillDir) | Out-Null
git clone https://github.com/xingyun7842/-.git $SkillDir
```

### macOS / Linux

```bash
mkdir -p "$HOME/.codex/skills"
git clone https://github.com/xingyun7842/-.git "$HOME/.codex/skills/weread-optimizer"
```

## Usage

Ask Codex to use the skill on a folder:

```text
[$weread-optimizer](~/.codex/skills/weread-optimizer/SKILL.md) Process this folder for WeRead EPUB output.
```

The core script processes the current directory by default:

```bash
python -X utf8 scripts/weread_optimize.py
```

Useful environment variables:

- `WEREAD_INPUT_DIR`: source folder to process.
- `WEREAD_OUTPUT_DIR`: output folder.
- `WEREAD_HTML_ONLY=1`: process only HTML files.
- `WEREAD_COMBINE_HTML=1`: combine HTML files into one EPUB collection.
- `WEREAD_COLLECTION_TITLE`: title for the combined EPUB.

## Notes

- PPT/PPTX conversion on Windows can use PowerPoint COM when PowerPoint is installed.
- Cloud/Linux environments can use the HTML/PDF/DOCX/TXT/image paths, but usually cannot use Windows PowerPoint COM.
- For very large image-heavy EPUBs, compress images before uploading to WeRead to avoid web import timeouts.
