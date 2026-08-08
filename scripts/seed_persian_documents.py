#!/usr/bin/env python3
# ============================================================
# Seed Persian Documents for RAG Testing
# ============================================================

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.db.session import SessionLocal
from src.app.services.ingestion.service import get_ingestion_service


async def main():
    print("📚 Seeding Persian (Farsi) documents for RAG testing...")
    
    db = SessionLocal()
    try:
        ingestion_service = get_ingestion_service(db)
        
        # Persian documents with metadata
        documents = [
            {
                "name": "rag_persian_intro.txt",
                "content": """
بازیابی-تولید افزوده (RAG) یک تکنیک است که بازیابی اطلاعات را با مدل‌های زبانی بزرگ ترکیب می‌کند 
تا پاسخ‌های دقیق‌تر و مرتبط‌تری تولید کند.

چگونه RAG کار می‌کند:
1. پردازش پرسش: سوال کاربر پردازش شده و به بردار تبدیل می‌شود.
2. بازیابی: اسناد یا بخش‌های مرتبط از پایگاه دانش بازیابی می‌شوند.
3. تقویت: اطلاعات بازیابی شده به متن درخواست اضافه می‌شود.
4. تولید: مدل زبانی پاسخ‌هایی مبتنی بر متن بازیابی شده تولید می‌کند.

مزایای RAG:
- دقت بالاتر با پایه‌گذاری پاسخ‌ها در داده‌های واقعی
- اطلاعات به‌روز بدون نیاز به بازآموزی مدل
- شفافیت با ارائه ارجاع به منابع
- کاهش توهمات با محدود کردن مدل به متن بازیابی شده
"""
            },
            {
                "name": "langgraph_persian.txt",
                "content": """
لنگ‌گراف یک کتابخانه قدرتمند برای ساخت برنامه‌های حالت‌دار و چندعاملی با مدل‌های زبانی بزرگ است. 
این کتابخانه قابلیت‌های لنگ‌چین را با ایجاد گراف‌های چرخه‌ای گسترش می‌دهد.

مفاهیم اصلی لنگ‌گراف:
1. حالت: وضعیت پایدار در طول اجرای گراف
2. گره‌ها: عملیاتی که وضعیت را تغییر می‌دهند
3. یال‌ها: جریان بین گره‌ها را تعریف می‌کنند
4. یال‌های شرطی: مسیریابی پویا بر اساس وضعیت
5. ذخیره‌سازی نقاط بازرسی: ذخیره و ادامه اجرای گراف

الگوهای عامل در لنگ‌گراف:
- ReAct (استدلال + اقدام): عامل‌های فراخوانی ابزار
- برنامه‌ریزی و اجرا: تجزیه ساختاری وظایف
- خوداصلاحی: اصلاح تدریجی پاسخ‌ها
- چندعاملی: همکاری چندین عامل
"""
            },
            {
                "name": "pgvector_persian.txt",
                "content": """
پی‌جی‌وکتور یک افزونه برای پایگاه داده پستگرس‌کیوال است که پشتیبانی از جستجوی شباهت بردارها را اضافه می‌کند.

ویژگی‌های کلیدی پی‌جی‌وکتور:
- ذخیره بردارها تا ۱۶۰۰۰ بعد
- جستجوی دقیق و تقریبی نزدیک‌ترین همسایه
- پشتیبانی از فاصله اقلیدسی، ضرب داخلی و شباهت کسینوسی
- نمایه‌سازی با IVFFlat برای جستجوی سریع تقریبی

عملیات رایج پی‌جی‌وکتور:
- ایجاد افزونه: CREATE EXTENSION vector;
- ایجاد جدول: CREATE TABLE items (embedding vector(1536));
- جستجو: SELECT * FROM items ORDER BY embedding <=> query_embedding LIMIT 5;
"""
            }
        ]
        
        # Check existing documents first
        from sqlalchemy import text
        result = db.execute(text("SELECT COUNT(*) FROM documents"))
        count = result.scalar()
        print(f"📊 Existing documents: {count}")
        
        if count == 0:
            for doc_data in documents:
                print(f"📄 Ingesting Persian: {doc_data['name']}...")
                doc = await ingestion_service.ingest_document(
                    content=doc_data["content"],
                    name=doc_data["name"],
                    source_path=f"seed://{doc_data['name']}",
                    doc_metadata={"language": "persian", "type": "sample_document"}
                )
                print(f"   ✅ ID: {doc.id}")
            
            print("\n✅ Persian seeding complete!")
        else:
            print(f"✅ Already have {count} documents. Skipping seeding.")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
