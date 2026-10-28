from kb_manager.web.app import app
for r in app.routes:
    print(getattr(r, "path", getattr(r, "prefix", "NONE")), getattr(r, "methods", None))
