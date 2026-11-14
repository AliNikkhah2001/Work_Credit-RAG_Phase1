# Edit instructions — Dual report polish (from user prompt 2026-11-10)

Apply to **both** PDFs (full technical report + security/networking brief). Rebuild after all edits. Do **not** edit the Cursor plan file.

## 1. Typography

1. Remove **Arial** / Arial Unicode MS from every role: body, TOC, headers, footers, monospace/code, tables.
2. Use **serif** fonts only.
   - Body + TOC + headings: TeX Gyre Pagella (or equivalent serif).
   - Monospace/code: TeX Gyre Cursor (serif mono) or Pagella at slightly smaller size — never Arial.
   - Persian snippets: download a **serif** Arabic/Persian face (e.g. Amiri) and use that; do not use Vazirmatn/Arial.
3. Technical terms, variables, ports, paths, env names, and other special entities must render as **bold** or *italic* in **non-black** colors (define stable colors in the LaTeX preamble and apply via `\texttt` / `\textbf` / `\emph` hooks).

## 2. Running headers / footers

1. Remove page header text **“Work Credit RAG”** everywhere.
2. Remove Persian header **“شرکت اعتبارسنجی ایران”** everywhere.
3. Keep page numbers in the footer; no branded header strings.

## 3. Page breaks

1. Every new **section** (`##` / `\section`) starts on a **new page**.
2. Chapters already clear the page; preserve that.

## 4. Cross-report silence

1. In the **full** report, do not mention the security briefing PDF or a two-PDF split.
2. In the **brief**, do not mention the full report or a two-PDF split.
3. Remove the entire “How the two PDFs are split” subsection (and any equivalent wording).

## 5. Executive / module overview (chapter ~1 / section 02)

1. **Remove** “Why the platform exists”.
2. **Remove** “How the two PDFs are split”.
3. **Remove** “Corpus, safety, and ambiguity at a glance” (section 1.4 / that heading).
4. **Remove Vast.ai** throughout this chapter; describe only the **H200 lab server**.
5. **Keep** “Module ownership” but **drop the Path/repo column** from the table (keep module, port, responsibility).
6. **Remove** “Design principles” (section 1.7 / that heading).

## 6. Hosting narrative (all chapters)

1. Remove **Vast.ai** / Vast instance / RTX 3090 MVP / `deploy/vast` / loopback `:18000` as a second host story.
2. Frame production as the **self-hosted H200 lab server** only (Manager `:9000`, embeds, Gemma pool, TRT, Docker data plane, Squid as needed).
3. Security chapter: **delete “Vast.ai listeners”** entirely.
4. Security § black-box / 3.2.1: state that the project runs on the self-hosted H200 server; rewrite dual-host diagrams/captions if needed so Vast is gone.

## 7. Security chapter specifics (section 11; brief numbering ~3.x)

1. **Attack taxonomy**: remove the **IDs** column entirely. Also remove any “Residual / re-verify” column or wording that implies unfinished work.
2. Rewrite taxonomy rows as descriptive class + severity + what the control/class covers — **positive/descriptive**, not a bug backlog.
3. **Guardrails architecture**: do **not** say NVIDIA NeMo is off the runtime path. Describe **only the current** signals → judge → self-check structure.
4. **Remove** “Authentication and edge controls” entirely.
5. **Remove** “Residual risks and tip gaps” entirely.
6. Scrub intro paragraphs that frame an open audit backlog, tip re-verify, or unfixed defects.

## 8. Global content policy (both reports)

**Never mention** in either PDF:

- todos / not done / pending / “still missing” / “may still”
- bugs / flaws / gaps / tip gaps / open issues
- audit “re-verify at tip” / “not fixed” / defect backlog language
- known missing routes or broken `hasattr` checks
- failed tests, OOM episodes framed as failures, “pending Hit@5”, etc.

Where a metric was “pending”, either omit it or state only published completed figures (e.g. v11 Hit@5) without calling out unfinished work.

Remove dedicated “Open tip gap” (and similar) subsections from KB / appendix / front matter.

## 9. Rebuild

1. Update `latex/preamble_classic.tex` (fonts, colors, empty headers, `\section` page breaks).
2. Update all `sections/*.md` per rules above; keep diagram assets that remain accurate after H200-only framing.
3. Run `python3 scripts/assemble_report.py` → refresh both PDFs under `out/`.
4. Smoke-check: cover logo-only, no Arial, no Vast, no flaw/todo language, no branded headers, sections start on new pages.
