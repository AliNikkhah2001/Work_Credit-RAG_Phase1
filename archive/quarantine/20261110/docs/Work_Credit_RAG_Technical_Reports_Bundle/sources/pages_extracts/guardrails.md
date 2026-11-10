# Guardrails — GitHub Pages extract

Sources: `components/guardrails/docs/{index,technical,high-level}.html`.

## Role

Persian-aware safety boundary + guarded Gemma gateway (`:8200`). Fail-closed: policy/timeout errors refuse rather than pass through. Orchestrator calls `POST /v1/rails/check` (input) then `POST /v1/chat/completions` (guarded generate → Gemma `:18000` Vast / Manager `:9000` H200).

## NeMo removed

- **nemoguardrails removed at runtime** — path is deterministic `signals` → policy/LLM or Mizan/hybrid judge → direct-LLM Yes/No self-check.
- `config/config.yml` and `config/rails.co` remain as legacy files; **not loaded or executed**.
- `nemoguardrails` may still appear in `pyproject.toml` but is not imported at runtime.
- Env `GUARD_NEMO_SELFCHECK` (`on` / `shadow` / `off`) kept for backward compatibility — controls the **direct-LLM self-check**, not NeMo.

## HurtLex allowlist size

**28 lemmas** in `kb/hurtlex_allowlist.json` — exact-word allowlist for input and output HurtLex hate checks (credit/social false-positive suppression). Profanity / PII / secret remain strict and are **not** allowlisted.

Examples: حذف، بخشی، تأمین مالی، اشتغال، پست، مصرف، هدف، نادرست، پستی، مهم، ضعیف، خسته، شرح، دسته، جزئی، ناشی، خوشحال، سخت، پلیس، بچه، گروه، مردم، دختر، خانم، پوست، قوم، روستایی، قشر.

## PII-IR checks (output rails)

Output stage deterministic signals include **PII-IR**:

- National ID — mod-11
- Sheba / IR-IBAN — mod-97
- Mobile / landline patterns

Valid PII → **mask-and-continue** (`[masked-pii]`); `secret` markers (`sk-`, `api_key`, `database_url`, `Bearer`) → **hard block**. Events log PII-masked only.

## Policy files

- Store: `policies/` — git-backed versioned prompts `policies/<domain>-v<semver>.yaml`
- Pin: `policies/active.yaml`
- Current example: `ics-credit-v1.0.0` (out-of-domain incl. company/people as in-domain; ungrounded-advice)
- Schema: `id` / `version` / `stage` / `categories` with `prompt` (`{{text}}` / `{{signals}}`), `refusal`, `examples`, plus `domain_keywords` for fast no-LLM out-of-domain pre-check
- Ship new versions by adding a file + moving the pin — never edit released versions
- Reported `POLICY_VERSION` default: `mvp-1`

## SVG inventory

Docs `images/` diagram assets (used on overview + technical pages):

| File | Depicts |
|---|---|
| `images/architecture-platform.svg` | Platform position: Orchestrator → Guardrails → Gemma |
| `images/internal-pipeline.svg` | Internal pipeline: signals → judge → self-check → output rails |
| `images/code-hierarchy.svg` | Component file tree (`src/`, `config/`, `kb/`, `policies/`, `tests/`, `images/`) |

Dashboard also renders live SVG plots (per-category/detector bars, 24h block timeline, stage donut) at `GET /dashboard`.

## Pipeline / judge (report facts)

- Detectors emit evidence only (injection, jailbreak, HurtLex hate, profanity, scope, PII) — do not block directly except secret.
- `GUARD_JUDGE_BACKEND`: `gemma` (default) | `mizan` | `hybrid`
- `GUARD_JUDGE_MODE`: `on-signal` (default) | `always`
- Taxonomy: `prompt_injection` · `jailbreak` · `hate` · `offense`/profanity · `pii` · `out_of_scope` · `secret` · `policy` · `engine_error`
- `finish_reason`: `stop` | `length` | `content_filter`
