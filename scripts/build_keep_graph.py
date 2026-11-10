#!/usr/bin/env python3
"""Build a reachability keep-graph for cleanup decisions.

Seeds: compose files, Dockerfiles, deploy scripts, Python entrypoints.
Walks COPY paths + Python imports recursively. Emits JSON + Mermaid.
"""
from __future__ import annotations

import ast
import json
import os
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "cleanup"

COMPOSE_GLOBS = [
    "deploy/compose/*.yml",
    "deploy/docker/docker-compose*.yml",
    "compose.mvp.yml",
]
SEED_FILES = [
    "deploy/vast/start.sh",
    "deploy/vast/stop.sh",
    "deploy/vast/health.sh",
    "Jenkinsfile",
    "deploy/compose/litellm.local.yaml",
    "litellm.yaml",
    "AGENTS.md",
    "components/tracing/app.py",
    "components/knowledgebase/kb-manager/run_server.py",
    "components/guardrails/src/work_rag_guardrails/api.py",
    "components/orchestrator/src/work_rag_orchestrator/api.py",
]

COPY_RE = re.compile(r"^\s*COPY\s+(.+)$", re.I | re.M)
FROM_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([\w\.]+)", re.M)


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except Exception:
        return str(p)


def expand_globs(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        out.extend(ROOT.glob(pat))
    return out


def parse_compose_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for m in re.finditer(r"(?:context|dockerfile|source):\s*([^\s#]+)", text):
        refs.add(m.group(1).strip().strip("\"'"))
    for m in re.finditer(r"-\s+\.?/?([^\s:]+\.(?:py|sh|yml|yaml|sql|json))", text):
        refs.add(m.group(1))
    return refs


def parse_dockerfile_copies(text: str, dockerfile: Path) -> set[Path]:
    files: set[Path] = set()
    base = dockerfile.parent
    for m in COPY_RE.finditer(text):
        parts = m.group(1).split()
        # drop flags like --from=
        parts = [p for p in parts if not p.startswith("--")]
        if len(parts) < 2:
            continue
        srcs, _dst = parts[:-1], parts[-1]
        for src in srcs:
            if src.startswith("http"):
                continue
            p = (base / src).resolve()
            if p.exists():
                if p.is_dir():
                    for child in p.rglob("*"):
                        if child.is_file() and "__pycache__" not in child.parts:
                            files.add(child)
                else:
                    files.add(p)
    return files


def python_imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    return mods


PACKAGE_ROOTS = {
    "kb_manager": ROOT / "components/knowledgebase/kb-manager/kb_manager",
    "work_rag_guardrails": ROOT / "components/guardrails/src/work_rag_guardrails",
    "work_rag_orchestrator": ROOT / "components/orchestrator/src/work_rag_orchestrator",
}


def resolve_local_module(mod: str, from_file: Path) -> Path | None:
    if mod in PACKAGE_ROOTS:
        init = PACKAGE_ROOTS[mod] / "__init__.py"
        return init if init.exists() else PACKAGE_ROOTS[mod]
    # relative same-package import walk for dotted paths under package roots
    for pkg, base in PACKAGE_ROOTS.items():
        if mod == pkg or mod.startswith(pkg + "."):
            rest = mod[len(pkg) :].lstrip(".")
            candidate = base / Path(*rest.split(".")) if rest else base
            if candidate.with_suffix(".py").exists():
                return candidate.with_suffix(".py")
            if (candidate / "__init__.py").exists():
                return candidate / "__init__.py"
    # same-dir relative modules
    sib = from_file.parent / f"{mod}.py"
    if sib.exists():
        return sib
    return None


def walk_python(entry: Path, keep: set[str], edges: dict[str, set[str]]) -> None:
    q: deque[Path] = deque([entry])
    seen: set[Path] = set()
    while q:
        cur = q.popleft()
        if cur in seen or not cur.exists() or cur.suffix != ".py":
            continue
        seen.add(cur)
        keep.add(rel(cur))
        for mod in python_imports(cur):
            tgt = resolve_local_module(mod, cur)
            if tgt is None:
                # try dotted import from same package using FROM imports fully
                continue
            edges[rel(cur)].add(rel(tgt))
            q.append(tgt)
        # also resolve full from X.Y import by re-parsing
        try:
            tree = ast.parse(cur.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                tgt = resolve_local_module(node.module, cur)
                if tgt is not None:
                    edges[rel(cur)].add(rel(tgt))
                    q.append(tgt)


def classify_unkept(keep: set[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = defaultdict(list)
    skip_parts = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache"}
    interesting_roots = [
        ROOT / "components",
        ROOT / "deploy",
        ROOT / "api",
        ROOT / "scripts",
        ROOT / "eval",
        ROOT / "dev",
        ROOT / "archive",
        ROOT / "deprecated",
        ROOT / "docs",
    ]
    for base in interesting_roots:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in skip_parts for part in p.parts):
                continue
            r = rel(p)
            if r in keep:
                continue
            low = r.lower()
            if any(x in low for x in ("/plot", "plots/", ".png", ".svg", "diagram")):
                buckets["plots_diagrams"].append(r)
            elif any(x in low for x in ("/docs/", "readme", ".md", "technical-report")):
                buckets["docs"].append(r)
            elif any(x in low for x in ("dataset", "/data/", "benchmark", "eval/")):
                buckets["data_datasets_eval"].append(r)
            elif any(x in low for x in ("research", "investigation", "/dev/", "archive/", "deprecated/")):
                buckets["research_archive_dev"].append(r)
            elif low.endswith((".py", ".sh", ".ipynb")):
                buckets["code_candidates_quarantine"].append(r)
            else:
                buckets["other"].append(r)
    return {k: sorted(v)[:5000] for k, v in buckets.items()}


def main() -> None:
    keep: set[str] = set()
    edges: dict[str, set[str]] = defaultdict(set)
    seeds: list[str] = []

    for s in SEED_FILES:
        p = ROOT / s
        if p.exists():
            keep.add(rel(p))
            seeds.append(rel(p))
            if p.suffix == ".py":
                walk_python(p, keep, edges)

    for comp in expand_globs(COMPOSE_GLOBS):
        keep.add(rel(comp))
        seeds.append(rel(comp))
        text = comp.read_text(encoding="utf-8", errors="ignore")
        for ref in parse_compose_refs(text):
            # resolve relative to compose file or repo root
            for base in (comp.parent, ROOT, ROOT / "deploy/compose"):
                cand = (base / ref).resolve()
                if cand.exists():
                    keep.add(rel(cand))
                    if cand.name.lower().startswith("dockerfile") or cand.name == "Dockerfile":
                        copies = parse_dockerfile_copies(
                            cand.read_text(encoding="utf-8", errors="ignore"), cand
                        )
                        for c in copies:
                            keep.add(rel(c))
                            if c.suffix == ".py":
                                walk_python(c, keep, edges)
                    elif cand.suffix == ".py":
                        walk_python(cand, keep, edges)
                    break

    # Dockerfiles under components
    for df in ROOT.glob("components/**/Dockerfile*"):
        keep.add(rel(df))
        copies = parse_dockerfile_copies(df.read_text(encoding="utf-8", errors="ignore"), df)
        for c in copies:
            keep.add(rel(c))
            if c.suffix == ".py":
                walk_python(c, keep, edges)

    # Explicit package entry walks
    for entry in (
        ROOT / "components/knowledgebase/kb-manager/kb_manager/web/app.py",
        ROOT / "components/guardrails/src/work_rag_guardrails/service.py",
        ROOT / "components/orchestrator/src/work_rag_orchestrator/graph.py",
    ):
        if entry.exists():
            walk_python(entry, keep, edges)

    classification = classify_unkept(keep)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "seed_count": len(seeds),
        "keep_count": len(keep),
        "seeds": sorted(seeds),
        "keep": sorted(keep),
        "edges": {k: sorted(v) for k, v in sorted(edges.items())},
        "classification": {k: {"count": len(v), "sample": v[:50]} for k, v in classification.items()},
        "classification_full_counts": {k: len(v) for k, v in classification.items()},
    }
    (OUT_DIR / "keep-graph.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (OUT_DIR / "classification.json").write_text(
        json.dumps(classification, indent=2), encoding="utf-8"
    )

    # Compact mermaid: seeds + first-hop only for readability
    lines = ["flowchart TD", "  classDef keep fill:#c6f6d5,stroke:#276749;", "  classDef seed fill:#9ae6b4,stroke:#22543d,stroke-width:2px;"]
    for i, s in enumerate(sorted(seeds)[:40]):
        nid = f"S{i}"
        label = s.replace('"', "'")
        lines.append(f'  {nid}["{label}"]:::seed')
    # include a few keep nodes from packages
    pkg_keeps = [k for k in sorted(keep) if k.endswith(".py") and "components/" in k][:60]
    for i, k in enumerate(pkg_keeps):
        nid = f"K{i}"
        lines.append(f'  {nid}["{k.replace(chr(34), chr(39))}"]:::keep')
    (OUT_DIR / "keep-graph.mmd").write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = [
        "# Keep-graph summary",
        "",
        f"Generated: `{payload['generated']}`",
        f"- Seeds: **{payload['seed_count']}**",
        f"- Keep (green) files: **{payload['keep_count']}**",
        "",
        "## Non-keep classification counts",
        "",
    ]
    for k, n in sorted(payload["classification_full_counts"].items()):
        summary.append(f"- `{k}`: {n}")
    summary.append("")
    summary.append("See `keep-graph.json`, `classification.json`, `keep-graph.mmd`.")
    (OUT_DIR / "keep-graph-summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps({"keep": payload["keep_count"], "classes": payload["classification_full_counts"]}, indent=2))


if __name__ == "__main__":
    main()
