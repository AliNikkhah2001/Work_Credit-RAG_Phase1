#!/usr/bin/env python3
"""Assemble markdown sections → classic/dense KOMA LaTeX → PDF set."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "sections"
OUT = ROOT / "out"
LATEX = ROOT / "latex"
CHAPTERS = LATEX / "chapters"

FULL_ORDER = [
    "01_front_matter.md",
    "02_executive_and_modules.md",
    "03_architecture_and_request.md",
    "04_dive_kb.md",
    "05_dive_orch.md",
    "06_dive_server.md",
    "07_dive_guard.md",
    "08_dive_telemetry.md",
    "09_benchmarks.md",
    "10_appendix.md",
    "11_security_networking.md",
]

BRIEF_EXTRA = [
    ("brief_executive.tex", "02_executive_and_modules.md"),
    ("brief_architecture.tex", "03_architecture_and_request.md"),
]

STANDALONE = [
    ("standalone_telemetry.md", "standalone_telemetry.tex"),
    ("standalone_server.md", "standalone_server.tex"),
    ("standalone_summary.md", "standalone_summary.tex"),
]

PDF_JOBS = [
    ("main_full.tex", "Work_Credit_RAG_Technical_Report.pdf"),
    ("main_security.tex", "Work_Credit_RAG_Security_Networking_Brief.pdf"),
    ("main_telemetry.tex", "Work_Credit_RAG_Telemetry_Monitoring_Brief.pdf"),
    ("main_server.tex", "Work_Credit_RAG_Server_Serving_Scaling_Brief.pdf"),
    ("main_summary.tex", "Work_Credit_RAG_Technical_Summary.pdf"),
]


def md_to_tex(md: str) -> str:
    tmp_in = LATEX / "_tmp_section.md"
    tmp_out = LATEX / "_tmp_section.tex"
    text = md.replace("](assets/", "](../assets/")
    tmp_in.write_text(text, encoding="utf-8")
    subprocess.check_call(
        [
            "pandoc",
            str(tmp_in),
            "-o",
            str(tmp_out),
            "--from=markdown",
            "--to=latex",
            "--top-level-division=chapter",
            "--wrap=none",
        ],
        cwd=ROOT,
    )
    tex = tmp_out.read_text(encoding="utf-8")
    tex = re.sub(r"\\tightlist\n", "", tex)
    tex = re.sub(r"\\includesvg(?:\[[^\]]*\])?\{[^}]+\}", r"---", tex)
    tex = re.sub(
        r"\\begin\{minipage\}\[b\]\{\\linewidth\}\\raggedright\s*(.*?)\s*\\end\{minipage\}",
        r"\1",
        tex,
        flags=re.S,
    )
    # Drop logo images still embedded in cells
    tex = re.sub(
        r"\\includegraphics(?:\[[^\]]*\])?\{[^}]*logos/[^}]+\}",
        "",
        tex,
    )
    tex = tex.replace(
        r"\includegraphics{",
        r"\includegraphics[width=0.88\linewidth,height=0.36\textheight,keepaspectratio]{",
    )
    tex = re.sub(
        r"\\includegraphics\[width=0\.88\\linewidth,height=0\.36\\textheight,keepaspectratio\](\[[^\]]*\])",
        r"\\includegraphics\1",
        tex,
    )
    tmp_in.unlink(missing_ok=True)
    tmp_out.unlink(missing_ok=True)
    return tex


def write_chapter(tex_name: str, md_path: Path) -> Path:
    CHAPTERS.mkdir(parents=True, exist_ok=True)
    out = CHAPTERS / (tex_name if tex_name.endswith(".tex") else Path(tex_name).stem + ".tex")
    body = md_to_tex(md_path.read_text(encoding="utf-8"))
    out.write_text(body, encoding="utf-8")
    print("chapter", out.name, "chars", len(body))
    return out


def compile_tex(main_name: str, pdf_name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = ["xelatex", "-interaction=nonstopmode", "-halt-on-error", main_name]
    for _ in range(2):
        subprocess.check_call(cmd, cwd=LATEX)
    produced = LATEX / main_name.replace(".tex", ".pdf")
    dest = OUT / pdf_name
    shutil.copy2(produced, dest)
    print("PDF", dest, "size", dest.stat().st_size)
    return dest


def assemble_chapters() -> None:
    for name in FULL_ORDER:
        write_chapter(name, SECTIONS / name)
    for tex_name, md_name in BRIEF_EXTRA:
        write_chapter(tex_name, SECTIONS / md_name)
    for md_name, tex_name in STANDALONE:
        write_chapter(tex_name, SECTIONS / md_name)


def build_pdfs() -> None:
    assemble_chapters()
    for main, pdf in PDF_JOBS:
        compile_tex(main, pdf)


def main() -> None:
    build_pdfs()


if __name__ == "__main__":
    main()
