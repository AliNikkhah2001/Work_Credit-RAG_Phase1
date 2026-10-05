import re
from pathlib import Path

path = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/search.html")
content = path.read_text()

old_input = '<input type="text" id="filter-input" class="form-control" placeholder="Sub-space Folder (e.g. اشخاص حقوقی)" style="max-width: 250px; font-size: 1.1rem; padding: 10px;">'
new_input = """<select id="filter-input" class="form-control" style="max-width: 250px; font-size: 1.1rem; padding: 10px;">
                <option value="">All Knowledge (Global)</option>
                <optgroup label="اشخاص حقوقی (Legal Entities)">
                    <option value="اشخاص حقوقی">All Legal Entities</option>
                    <option value="اعتبارسنجی تسهیلات"> - اعتبارسنجی تسهیلات</option>
                    <option value="عضویت در پایگاه داده اعتباری به عنوان تامین کننده اطلاعات"> - تامین کننده اطلاعات</option>
                    <option value="گزارش اعتبارسنجی مشتریان من"> - مشتریان من</option>
                </optgroup>
                <optgroup label="اشخاص حقیقی (Individuals)">
                    <option value="اشخاص حقیقی">All Individuals</option>
                    <option value="گزارش اعتبارسنجی چک"> - اعتبارسنجی چک</option>
                    <option value="گزارش اعتبارسنجی مشتریان من (مرتبط با کسب‌وکارها)"> - مشتریان من (کسب‌وکارها)</option>
                    <option value="اعتبارسنجی تسهیلات"> - اعتبارسنجی تسهیلات</option>
                </optgroup>
                <optgroup label="عمومی (General)">
                    <option value="پایگاه دانش عمومی">پایگاه دانش عمومی</option>
                </optgroup>
            </select>"""

if old_input in content:
    content = content.replace(old_input, new_input)
    path.write_text(content)
    print("search.html select box updated")
else:
    print("could not find old input in search.html")
