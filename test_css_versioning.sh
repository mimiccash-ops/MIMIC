#!/bin/bash
# Test CSS versioning and verify it works

echo "🧪 Тестую версіонування CSS файлів..."

cd /var/www/mimic || exit 1
source venv/bin/activate

# 1. Тестую функцію версіонування
echo ""
echo "📝 Тестую функцію static_file_version:"
python3 test_versioning.py 2>&1

# 2. Перевіряю, чи генерується правильний HTML
echo ""
echo "🌐 Перевіряю HTML з версіонуванням:"
python3 -c "
from app import app
with app.app_context():
    from flask import render_template_string
    template = '<link rel=\"stylesheet\" href=\"{{ static_version(\"css/tailwind.css\") }}\">'
    html = render_template_string(template)
    print(f'Generated HTML: {html}')
    if '?v=' in html:
        print('✅ Версіонування працює!')
    else:
        print('❌ Версіонування не працює!')
" 2>&1

# 3. Перевіряю реальний URL через curl
echo ""
echo "🌐 Тестую реальний запит:"
curl -s "https://mimiccash.com/" | grep -o 'href="[^"]*tailwind\.css[^"]*"' | head -1

echo ""
echo "✅ Тест завершено"
