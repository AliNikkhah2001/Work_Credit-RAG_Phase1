# Tester Credentials — ICS RAG Evaluation

> **Login URL:** `http://127.0.0.1:13000` (Open WebUI — select `ICS Helper` at top)
> **Dashboard URL:** `http://127.0.0.1:3000/dashboard/observability` (traces, evaluations, pipeline)
> **RAG model:** `ics-helper-agent` (NOT arena)

| # | Username | Password | Display name |
|---|----------|----------|--------------|
| 01 | `tester01@ics.local` | `Tester2024!` | Tester 01 |
| 02 | `tester02@ics.local` | `Tester2024!` | Tester 02 |
| 03 | `tester03@ics.local` | `Tester2024!` | Tester 03 |
| 04 | `tester04@ics.local` | `Tester2024!` | Tester 04 |
| 05 | `tester05@ics.local` | `Tester2024!` | Tester 05 |
| 06 | `tester06@ics.local` | `Tester2024!` | Tester 06 |
| 07 | `tester07@ics.local` | `Tester2024!` | Tester 07 |
| 08 | `tester08@ics.local` | `Tester2024!` | Tester 08 |
| 09 | `tester09@ics.local` | `Tester2024!` | Tester 09 |
| 10 | `tester10@ics.local` | `Tester2024!` | Tester 10 |
| 11 | `tester11@ics.local` | `Tester2024!` | Tester 11 |
| 12 | `tester12@ics.local` | `Tester2024!` | Tester 12 |
| 13 | `tester13@ics.local` | `Tester2024!` | Tester 13 |
| 14 | `tester14@ics.local` | `Tester2024!` | Tester 14 |
| 15 | `tester15@ics.local` | `Tester2024!` | Tester 15 |
| 16 | `tester16@ics.local` | `Tester2024!` | Tester 16 |
| 17 | `tester17@ics.local` | `Tester2024!` | Tester 17 |
| 18 | `tester18@ics.local` | `Tester2024!` | Tester 18 |
| 19 | `tester19@ics.local` | `Tester2024!` | Tester 19 |
| 20 | `tester20@ics.local` | `Tester2024!` | Tester 20 |

## Admin
- `admin@localhost` / `test` (role: admin)

## How to use

### Star scoring (in chat)
- Click the **stars** at the bottom of any assistant reply (you see `☆☆☆☆☆`).
- Or click the **Star Rating** button under the assistant message → picks stars → `/rate 5 accurate #helpful` → saved to `observability.db`.

### Report a problem
- Click **Report Problem** under a reply → pick a category:
  `inaccurate` / `incomplete` / `hallucination` / `wrong_source` / `off_topic` / `other`
- Or send chat command: `/report inaccurate The year is wrong #fact-error`

### Retrieved content
- Click **Retrieved Content** under any reply → full KB chunks dumped directly (title, heading, BOTH/CE/RRF score, 600-char preview + expand, stage timing, citations).

### Persistence
- Chats are in `webui.db`; traces/evaluations are in separate `observability.db` (`/tmp/observability.db` → `docker-data/volumes/docker_trace-data/_data`) and `/tmp/langfuse_traces.jsonl`.
- **Deleting a chat in WebUI does NOT delete its trace** in observability — every request survives with timestamp, model, retrieved_chunks, stage_timing, and user_id.
- Admin can export all evaluations: `/api/observability/export?format=jsonl` or dashboard **Export** tab.

## Security note
> This file lives on a private/internal repo and contains **default test passwords**. Change them immediately in `Settings → Users` for any tester who leaves the pool. Never commit a real `litellm.env` or `WEBUI_SECRET_KEY`.

