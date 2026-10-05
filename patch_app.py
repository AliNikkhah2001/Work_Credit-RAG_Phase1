from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/app.py")
content = path.read_text()

# Add to import
content = content.replace("    zip_browser,\n)", "    zip_browser,\n    settings,\n)")

# Add include_router
router_line = 'app.include_router(settings.router, prefix="/settings", tags=["settings"])\n'
if "settings.router" not in content:
    content = content.replace('app.include_router(documents.router, prefix="/documents", tags=["documents"])', router_line + 'app.include_router(documents.router, prefix="/documents", tags=["documents"])')

path.write_text(content)
print("app.py patched.")
