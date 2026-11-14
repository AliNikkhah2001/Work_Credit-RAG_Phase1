import asyncio

from work_rag_orchestrator.clients.knowledgebase import KnowledgebaseClient
from work_rag_orchestrator.nodes.retrieve import _entity_tool_relevant, trim_supplemental

q = "در فهرست عناوین وام‌ها، وام ازدواج بانک تجارت هست یا نه؟"


async def main() -> None:
    print(
        "tool relevant",
        _entity_tool_relevant(
            q,
            {
                "filter_path": "اشخاص حقیقی/اعتبارسنجی تسهیلات",
                "applied_subspace": "facilities_person",
            },
        ),
    )
    async with KnowledgebaseClient() as c:
        ents = await c.supplementary_search(q, threshold=0.3, subspace="facilities_person")
    print(
        "raw",
        [
            (
                e.get("list_name"),
                len((e.get("content") or {}).get("records") or []),
                (e.get("content") or {}).get("_meta", {}).get("kind"),
            )
            for e in ents
        ],
    )
    trimmed = trim_supplemental(ents, q)
    for e in trimmed:
        c = e.get("content") or {}
        recs = c.get("records") or []
        print("trimmed", e.get("list_name"), "keys", list(c.keys()), "nrec", len(recs))
        print(" sample", recs[:8])
        print(" has تجارت", any("تجارت" in str(r) for r in recs))
        print(" groups", (c.get("groups") or [])[:4])


if __name__ == "__main__":
    asyncio.run(main())
