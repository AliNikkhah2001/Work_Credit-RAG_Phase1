# Work Credit RAG — Technical Report

Classic KOMA-Script (`scrreprt`) documentation for **شرکت اعتبارسنجی ایران** / Work Credit RAG Phase 1.

## Deliverables (PDF)

| Artifact | Path |
|---|---|
| Full technical report | [`out/Work_Credit_RAG_Technical_Report.pdf`](out/Work_Credit_RAG_Technical_Report.pdf) |
| Security & networking brief | [`out/Work_Credit_RAG_Security_Networking_Brief.pdf`](out/Work_Credit_RAG_Security_Networking_Brief.pdf) |
| Telemetry / monitoring brief | [`out/Work_Credit_RAG_Telemetry_Monitoring_Brief.pdf`](out/Work_Credit_RAG_Telemetry_Monitoring_Brief.pdf) |
| Server / serving / scaling brief | [`out/Work_Credit_RAG_Server_Serving_Scaling_Brief.pdf`](out/Work_Credit_RAG_Server_Serving_Scaling_Brief.pdf) |
| Dense technical summary (≤15 pp target) | [`out/Work_Credit_RAG_Technical_Summary.pdf`](out/Work_Credit_RAG_Technical_Summary.pdf) |
| Section drafts | [`sections/`](sections/) (01–11 + standalones) |
| LaTeX | [`latex/`](latex/) (`preamble_classic.tex`, `preamble_dense.tex`, `main_*.tex`) |

HTML (`out/index.html`) may be stale.

## Rebuild

```bash
# Mermaid → PNG (requires Chrome + npx)
bash scripts/render_diagrams.sh

# Sections → classic XeLaTeX → both PDFs
python3 scripts/assemble_report.py
# or: bash scripts/build_pdf.sh
```

## Notes

- Prose is original synthesis from GitHub Pages extracts plus code/architecture sources.
- Cover page is logo-only (ICS mark); body uses TeX Gyre Pagella / Heros with Arial Unicode MS for Persian glyphs.
- Tip gaps (`hasattr(dense, "model")`, missing `POST /search/supplement`) and audit findings are **not** marked fixed without tip verification.
- Do not invent benchmark numbers; tables cite Pages / `bench_report_latest` / KB latency notes.
