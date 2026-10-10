# Tester Credentials — ICS RAG Evaluation

> **Login:** `http://127.0.0.1:13000` (Open WebUI — select **ICS Helper** at top, NOT Arena — Arena is disabled)
> **Dashboard:** `http://127.0.0.1:3000/dashboard/observability` (traces, evaluations, pipeline, export)
> **All tester passwords:** `Tester2024!` — change after first login via Settings → Profile → Change Password.
> **Admin:** `admin@localhost` / `test` — role: `admin` (has Users/Functions/Models management).

| # | Username (email) | Password | Display name (obviously fake — not real person) |
|---|------------------|----------|--------------------------------------------------|
| 01 | `tester01@ics.local` | `Tester2024!` | TestAccount_01 |
| 02 | `tester02@ics.local` | `Tester2024!` | TestAccount_02 |
| 03 | `tester03@ics.local` | `Tester2024!` | DemoTester_03 |
| 04 | `tester04@ics.local` | `Tester2024!` | DemoTester_04 |
| 05 | `tester05@ics.local` | `Tester2024!` | EvalUser_05 |
| 06 | `tester06@ics.local` | `Tester2024!` | EvalUser_06 |
| 07 | `tester07@ics.local` | `Tester2024!` | QA_Fake_07 |
| 08 | `tester08@ics.local` | `Tester2024!` | QA_Fake_08 |
| 09 | `tester09@ics.local` | `Tester2024!` | Dummy_09 |
| 10 | `tester10@ics.local` | `Tester2024!` | Dummy_10 |
| 11 | `tester11@ics.local` | `Tester2024!` | MockAccount_11 |
| 12 | `tester12@ics.local` | `Tester2024!` | MockAccount_12 |
| 13 | `tester13@ics.local` | `Tester2024!` | SampleTest_13 |
| 14 | `tester14@ics.local` | `Tester2024!` | SampleTest_14 |
| 15 | `tester15@ics.local` | `Tester2024!` | Placeholder_15 |
| 16 | `tester16@ics.local` | `Tester2024!` | Placeholder_16 |
| 17 | `tester17@ics.local` | `Tester2024!` | SimUser_17 |
| 18 | `tester18@ics.local` | `Tester2024!` | SimUser_18 |
| 19 | `tester19@ics.local` | `Tester2024!` | Synthetic_19 |
| 20 | `tester20@ics.local` | `Tester2024!` | Synthetic_20 |

## Admin
- `admin@localhost` / `test` — role: `admin` — use for Users/Functions/Models management.
- Login goes to **Login page** when you open `http://127.0.0.1:13000` (the app redirects to `/auth` if no valid token). If you see the chat directly, click the avatar (top-right) → **Sign out**, then the login page appears.

## How testers use the chat (ICS Helper only)
1. Open `http://127.0.0.1:13000`.
2. **Sign in** → `testerNN@ics.local` / `Tester2024!`.
3. Select **`ICS Helper`** at the top of the chat box (not `Arena` — disabled).
4. Send a question → under each assistant reply there are **4 buttons** (ICS only):
   - **Star Rating** — 1–5 stars with comment/tags (or type `/rate 5 Great #helpful`)
   - **Report Problem** — 6 categories `inaccurate/incomplete/hallucination/wrong_source/off_topic/other` via `/report inaccurate ...`
   - **Retrieved Content** — dumps the KB chunks (Title/Heading/Source/score + 600-char preview), stage timing, citations
   - **Ground Truth** — ` /truth The correct answer is: ...` — save what the true response should be (stored with `tag ground_truth`)
5. Also available as chat commands: `/rate N comment #tag`, `/report <category> comment #tag`, `/truth The correct answer is …`

## Logs & traces (persistent)
- **WebUI chats** (`/app/backend/data/webui.db`, table `chat`/`chat_message`) — kept even after a user clicks "Delete chat" in the UI? **No — WebUI deletion DOES remove the `chat` row** — but **observability logs are separate and permanent**:
  - **Traces** (`/tmp/observability.db`, table `traces`) — holds `request_id`, `user_query`, `retrieved_chunks`, `stage_timing`, `response`, `citations`, `created_at`, etc. — **never deleted when a chat is removed**.
  - **Evaluations** (same DB, table `evaluations`) — holds `rating`, `comment`, `tags`, `report_category` (`[REPORT:...]`), `ground_truth` (`[GROUND_TRUTH] ...`), `user_id`, `created_at` — **never deleted when a chat is removed**.
  - **Fallback collector** (`/tmp/langfuse_traces.jsonl` + `/tmp/pipeline_traces.jsonl`) — append-only JSONL, also permanent.
- **Timestamps:** every chat message has `created_at`/`updated_at` (WebUI `chat_message` table); every trace/evaluation has `created_at` (float epoch, shown as local time in dashboard).

## Security note
> This file lives on a private/internal repo and contains **default test passwords**. Change them immediately in `Settings → Users` for any tester who leaves the pool. Never commit a real `litellm.env` or `WEBUI_SECRET_KEY`.

## Notes
- All display names are **obviously fake** test accounts (`TestAccount_01`, `DemoTester_03`, `QA_Fake_07`, etc.) — not real company personnel.
- Removing a tester in `Admin → Users → Delete` does **not** delete their prior traces/evaluations — the `evaluations.user_id` and `traces.user_id` remain in `observability.db` for audit.
