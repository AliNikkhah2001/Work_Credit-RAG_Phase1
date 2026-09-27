"""Migrate KB sqlite (kb_1405.db) -> postgres pgvector DB. Preserves UUIDs."""
import json
import sqlite3
import sys

from sqlalchemy import create_engine, text

SRC = "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager/data/kb_1405.db"
DST = "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/kb_manager"


def adapt_rows(con, table):
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    rows = con.execute(f"SELECT * FROM {table}").fetchall()
    return cols, rows


def main():
    scon = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    engine = create_engine(DST)
    with engine.begin() as pg:
        # create schema via app models
        sys.path.insert(0, "/workspace/Work_Credit-RAG_Phase1/components/knowledgebase/kb-manager")
        from kb_manager.models.database import Base

        Base.metadata.create_all(engine)
        for table in ["documents", "chunks", "document_versions", "ingestion_jobs"]:
            cols, rows = adapt_rows(scon, table)
            if table == "chunks" and "embedding" in cols:
                # pinned code model has no embedding column; dense vectors
                # come from dense_embeddings.npz at query time
                idx = cols.index("embedding")
                cols = [c for c in cols if c != "embedding"]
                rows = [tuple(v for j, v in enumerate(r) if j != idx) for r in rows]
            print(f"{table}: {len(rows)} rows x {len(cols)} cols")
            if not rows:
                continue
            col_list = ", ".join(f'"{c}"' for c in cols)
            bool_idx = {i for i, c in enumerate(cols) if c in ("is_verified",)}
            for r in rows:
                vals = []
                for i, v in enumerate(r):
                    if isinstance(v, (dict, list)):
                        vals.append(json.dumps(v, ensure_ascii=False))
                    elif i in bool_idx and v is not None:
                        vals.append(bool(v))
                    else:
                        vals.append(v)
                placeholders = ", ".join([f":p{i}" for i in range(len(vals))])
                pg.execute(
                    text(f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'),
                    {f"p{i}": vals[i] for i in range(len(vals))},
                )
    with engine.begin() as pg:
        for t in ["documents", "chunks", "document_versions", "ingestion_jobs"]:
            n = pg.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            print(f"pg {t}: {n}")


if __name__ == "__main__":
    main()
