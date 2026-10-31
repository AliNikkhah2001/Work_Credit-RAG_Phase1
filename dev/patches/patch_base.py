from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/base.html")
content = path.read_text()

# Add to navbar
nav_link = '<li><a href="/settings" class="nav-link {% if \'/settings\' in request.url.path %}active{% endif %}">Settings</a></li>\n'
if "/settings" not in content:
    content = content.replace('<li><a href="/benchmarks"', nav_link + '                <li><a href="/benchmarks"')

path.write_text(content)
print("base.html patched.")
