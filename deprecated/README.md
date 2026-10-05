# Deprecated Files — Reconstruction Guide

These files were moved here on **2026-09-27** during a repository cleanup.
They are preserved for reference but are **no longer part of the active project**.

## How to Restore Any File

Each subfolder contains a `MANIFEST.txt` listing original paths.
You can also restore from git history:

```bash
# Find the file in git history
git log --all --full-history -- <original-path>

# Restore it to its original location
git checkout <commit-hash> -- <original-path>
```

## Categories

### 1. Stale Planning Docs (`plans/`)
Planning documents that were completed or superseded.
Most originals were already archived in `archive/plans/` during an earlier cleanup;
these are the leftover pointer stubs and historical RFCs.

### 2. Redundant Audit Docs (`audits/`)
Multiple AI-generated audit documents describing the same findings.
The canonical audit is kept at `docs/history/CODE_AUDIT_2026-09-27.md`.

### 3. Session-Specific Deploy Artifacts (`session-artifacts/`)
Vast.ai deployment scripts with hardcoded IPs, instance IDs,
session-specific data, and **hardcoded secrets** (API keys, DB passwords).
General deployment procedures remain in `deploy/vast/start.sh`, `deploy/vast/stop.sh`,
and `deploy/vast/health.sh`.

### 4. Obsolete Scripts (`obsolete/`)
Scripts with `src/` imports or abandoned approaches that cannot
work with the current `components/` directory structure.
