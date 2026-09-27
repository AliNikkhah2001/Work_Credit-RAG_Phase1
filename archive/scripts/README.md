# Archived Scripts

Utilities moved from `scripts/` — not in `deploy/vast/start.sh` hot path.

| Script | Reason |
|--------|--------|
| `test_runner_tui.py/.sh` (17+15KB) | TUI test runner, interactive — not used in headless Vast |
| `mock_gemma_manager.py` | Mock for offline tests, superseded by `llama-server :18000` |
| `bootstrap_gpu_machine.sh` | One-off GPU bootstrap, now in `deploy/vast/start.sh` |
| `debug_hurtlex.py` (1.2KB) | HurtLex debug, covered by `guardrails/tests/` |

Restore: `git mv archive/scripts/<file> scripts/`
