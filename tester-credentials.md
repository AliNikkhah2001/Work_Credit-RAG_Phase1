# Tester Credentials — ICS RAG Evaluation

> **Login:** `http://127.0.0.1:13000` (Open WebUI — ICS Helper Agent)
> **Dashboard:** `http://127.0.0.1:3000/dashboard/observability` (traces, evaluations, pipeline, export)
> **All passwords:** `Tester2024!`  —  **change after first login via Settings → Profile → Change Password.**

| # | Username (email) | Display name | Password |
|---|------------------|--------------|----------|
| 01 | `tester01@ics.local` | علی رضایی | `Tester2024!` |
| 02 | `tester02@ics.local` | سارا احمدی | `Tester2024!` |
| 03 | `tester03@ics.local` | محمد حسینی | `Tester2024!` |
| 04 | `tester04@ics.local` | زهرا کریمی | `Tester2024!` |
| 05 | `tester05@ics.local` | حسین موسوی | `Tester2024!` |
| 06 | `tester06@ics.local` | مریم جعفری | `Tester2024!` |
| 07 | `tester07@ics.local` | رضا نوری | `Tester2024!` |
| 08 | `tester08@ics.local` | نرگس اکبری | `Tester2024!` |
| 09 | `tester09@ics.local` | امیر عباسی | `Tester2024!` |
| 10 | `tester10@ics.local` | لیلا محمدی | `Tester2024!` |
| 11 | `tester11@ics.local` | جواد کاظمی | `Tester2024!` |
| 12 | `tester12@ics.local` | شیرین صادقی | `Tester2024!` |
| 13 | `tester13@ics.local` | فرهاد بهرامی | `Tester2024!` |
| 14 | `tester14@ics.local` | پریسا نیک‌نژاد | `Tester2024!` |
| 15 | `tester15@ics.local` | کوروش فرهادی | `Tester2024!` |
| 16 | `tester16@ics.local` | الهام قاسمی | `Tester2024!` |
| 17 | `tester17@ics.local` | بهنام شریفی | `Tester2024!` |
| 18 | `tester18@ics.local` | نازنین طاهری | `Tester2024!` |
| 19 | `tester19@ics.local` | آرش علوی | `Tester2024!` |
| 20 | `tester20@ics.local` | نگار یزدانی | `Tester2024!` |

## How to log in
1. Open `http://127.0.0.1:13000`.
2. Click **Sign in** → enter `testerNN@ics.local` / `Tester2024!` → **Sign in**.
   (If login is skipped because `WEBUI_AUTH=false`, users are still pre-created — set `WEBUI_AUTH=true` to enforce.)
3. Select **`ICS Helper`** at the top of the chat box (not `Arena Model`).
4. Send a question, then use the action buttons under each assistant reply:
   - **Star Rating** — 1–5 stars with comment/tags
   - **Report Problem** — pick a category (`inaccurate`/`incomplete`/`hallucination`/…)
   - **Retrieved Content** — dump the KB chunks, stage timing, and citations

## Logs & traces (persistent)
- **WebUI chats** (`/app/backend/data/webui.db`, table `chat`) — kept even after a user clicks "Delete chat" in the UI? **No — WebUI deletion DOES remove the `chat` row** — but the **observability logs are separate and permanent**:
  - **Traces** (`/tmp/observability.db`, table `traces`) — holds `request_id`, `user_query`, `retrieved_chunks`, `stage_timing`, `response`, `citations`, `created_at`, etc. — **never deleted when a chat is removed**.
  - **Evaluations** (same DB, table `evaluations`) — holds `rating`, `comment`, `tags`, `user_id`, `report_category`, `created_at` — **never deleted when a chat is removed**.
  - **Fallback collector** (`/tmp/langfuse_traces.jsonl` + `/tmp/pipeline_traces.jsonl`) — append-only JSONL, also permanent.
- **Timestamps:** every chat message has `created_at`/`updated_at` (WebUI `chat_message` table); every trace/evaluation has `created_at` (float epoch).

## Admin
- `admin@localhost` / `test` — already present, role `admin`.
- Do **not** commit real `litellm.env` or `WEBUI_SECRET_KEY` — use `litellm.env.example`.

## Security note
This file contains default test passwords. The repo is intended to be **private** or access-controlled. If private-deployment only, change passwords immediately after distribution. Remove this file from public forks.
