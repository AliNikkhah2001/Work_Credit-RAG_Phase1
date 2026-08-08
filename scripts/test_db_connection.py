#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.db.session import SessionLocal
from sqlalchemy import text

def test_db():
    print("🔍 Testing database connection...")
    
    try:
        db = SessionLocal()
        result = db.execute(text("SELECT 1"))
        print("✅ Database connection successful!")
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_db()
