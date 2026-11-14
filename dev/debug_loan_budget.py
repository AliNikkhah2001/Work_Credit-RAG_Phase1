import asyncio
import json
import re

from work_rag_orchestrator.clients.knowledgebase import KnowledgebaseClient
from work_rag_orchestrator.nodes.retrieve import trim_supplemental

q = "در فهرست عناوین وام‌ها، وام ازدواج بانک تجارت هست یا نه؟"


def compact(content):
    if not isinstance(content, dict):
        return {"value": content}
    out = {}
    meta = content.get("_meta")
    if isinstance(meta, dict):
        out["_meta"] = {
            k: meta.get(k)
            for k in ("kind", "model", "count", "fields", "score_scale", "subspace_ids")
            if meta.get(k) is not None
        }
    for key in ("groups", "color_groups", "records", "bands"):
        if key in content:
            out[key] = content[key]
    return out


def relevance(ent, q):
    name = str(ent.get("list_name") or "")
    desc = str(ent.get("description") or "")
    content = ent.get("content") or {}
    meta = content.get("_meta") if isinstance(content, dict) else {}
    kind = str((meta or {}).get("kind") or "")
    blob = f"{name} {desc} {kind}".lower()
    score = float(ent.get("similarity") or 0.0)
    tokens = [t for t in re.split(r"[\s،,.؟?!:/()\-]+", (q or "").lower()) if len(t) >= 2]
    score += sum(1.5 for t in tokens if t in blob)
    if kind in {
        "shareholders",
        "loan_catalog",
        "data_providers",
        "report_consumers",
        "score_table",
    }:
        score += 2.0
    if any(k in (q or "") for k in ("سهامدار", "وام", "تامین", "لندتک", "ریسلر", "امتیاز", "رتبه", "رنگ")):
        if any(k in name for k in ("سهامدار", "وام", "تامین", "استفاده", "امتیاز")):
            score += 3.0
    return score


async def main() -> None:
    async with KnowledgebaseClient() as c:
        ents = await c.supplementary_search(q, threshold=0.3, subspace="facilities_person")
    trimmed = trim_supplemental(ents, q)
    ranked = sorted(trimmed, key=lambda e: relevance(e, q), reverse=True)
    budget = 9000
    used = 0
    for e in ranked:
        content = compact(e.get("content") or {})
        data = json.dumps(content, ensure_ascii=False)
        desc = str(e.get("description") or "")[:220]
        name = e.get("list_name")
        header = f"List: {name}\nDescription: {desc}\nData: "
        room = budget - used - len(header)
        if room < 300:
            print("STOP before", name, "used", used)
            break
        if len(data) > room:
            data = data[:room] + "…"
        block = header + data
        used += len(block)
        has = "تجارت" in block and "ازدواج" in block
        print(
            f"include {name} score={relevance(e, q):.1f} "
            f"block_chars={len(block)} used={used} has_loan_hit={has}"
        )


if __name__ == "__main__":
    asyncio.run(main())
