import sqlite3
from pathlib import Path

db_path = Path("components/knowledgebase/kb-manager/data/kb_test.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create entity_lists table
cur.execute("""
CREATE TABLE IF NOT EXISTS entity_lists (
    id VARCHAR(36) PRIMARY KEY,
    list_name VARCHAR(256) NOT NULL,
    description TEXT,
    description_embedding BLOB,
    content_json JSON NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
print("Database schema updated with entity_lists.")
