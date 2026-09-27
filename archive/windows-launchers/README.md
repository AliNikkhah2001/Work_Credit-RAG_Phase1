# Windows Launchers (archived)

Linux host uses `deploy/vast/start.sh` + `scripts/run_mvp.sh`. Windows artifacts archived:

| File | Origin | Reason |
|------|--------|--------|
| `run_mvp.ps1` | `scripts/` | PowerShell duplicate of `run_mvp.sh` |
| 17 `.bat`/`.ps1` | `components/knowledgebase/archive/windows-launchers/` | Vast is Linux-only, no `cmd.exe` |

Restore: `git mv archive/windows-launchers/<file> scripts/`
