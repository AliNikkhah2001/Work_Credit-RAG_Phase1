"""Export opencode session transcript to markdown (user prompts + assistant text + tool names)."""
import json
import sqlite3
import sys

SID = sys.argv[1] if len(sys.argv) > 1 else "ses_f6b058c02ffej8lpFUThWHsld0"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/opencode/session_export.md"

con = sqlite3.connect("/root/.local/share/opencode/opencode.db")
con.row_factory = sqlite3.Row
msgs = []
for r in con.execute(
    "select m.id, m.time_created, m.data from message m where m.session_id=? order by m.time_created", (SID,)):
    try:
        md = json.loads(r["data"])
    except Exception:
        md = {}
    role = md.get("role", md.get("info", {}).get("role", "unknown"))
    msgs.append((r["id"], str(role), r["time_created"]))
parts = {}
for r in con.execute("select message_id, data from part where session_id=? order by time_created", (SID,)):
    parts.setdefault(r["message_id"], []).append(json.loads(r["data"]))

out = [f"# Opencode session export\n\nSession: `{SID}`\nMessages: {len(msgs)}\n"]
for mid, role, _t in msgs:
    role = role.upper()
    out.append(f"\n## [{role}]\n")
    for p in parts.get(mid, []):
        t = p.get("type", "")
        if t == "text":
            txt = p.get("text", "")
            if len(txt) > 3000:
                txt = txt[:3000] + "\n…[truncated]…"
            out.append(txt + "\n")
        elif t == "tool":
            out.append(f"(tool: {p.get('tool', p.get('name', '?'))})\n")
        elif t == "reasoning":
            continue
        else:
            s = json.dumps(p)[:300]
            out.append(f"({t}: {s})\n")
open(OUT, "w").write("\n".join(out))
print(f"wrote {OUT} ({len(chr(10).join(out))//1024} KB)")
