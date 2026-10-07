from pathlib import Path
path = Path("components/knowledgebase/kb-manager/kb_manager/web/templates/search.html")
content = path.read_text()

old = """                <optgroup label="اشخاص حقوقی (Legal Entities)">
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
                </optgroup>"""

new = """                <optgroup label="اشخاص حقوقی (Legal Entities)">
                    <option value="اشخاص حقوقی">All Legal Entities</option>
                    <option value="اشخاص حقوقی/اعتبارسنجی تسهیلات"> - اعتبارسنجی تسهیلات</option>
                    <option value="اشخاص حقوقی/عضویت در پایگاه داده اعتباری به عنوان تامین کننده اطلاعات"> - تامین کننده اطلاعات</option>
                    <option value="اشخاص حقوقی/گزارش اعتبارسنجی مشتریان من"> - مشتریان من</option>
                </optgroup>
                <optgroup label="اشخاص حقیقی (Individuals)">
                    <option value="اشخاص حقیقی">All Individuals</option>
                    <option value="اشخاص حقیقی/گزارش اعتبارسنجی چک"> - اعتبارسنجی چک</option>
                    <option value="اشخاص حقیقی/گزارش اعتبارسنجی مشتریان من (مرتبط با کسب‌وکارها)"> - مشتریان من (کسب‌وکارها)</option>
                    <option value="اشخاص حقیقی/اعتبارسنجی تسهیلات"> - اعتبارسنجی تسهیلات</option>
                </optgroup>"""

content = content.replace(old, new)
path.write_text(content)
