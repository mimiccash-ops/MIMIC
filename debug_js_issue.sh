#!/bin/bash
# Debug JavaScript loading issue

echo "🔍 Діагностика проблеми з JavaScript..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірка, чи функція static_version працює
echo "📝 1. Тестую функцію static_version:"
source venv/bin/activate
python3 test_template_rendering.py 2>&1 | head -20

# 2. Перевірка реального HTML
echo ""
echo "🌐 2. Перевірка реального HTML (перші 50 рядків з script):"
curl -s "https://mimiccash.com/" | grep -i "script" | head -10

# 3. Перевірка, чи є помилки в логах
echo ""
echo "📋 3. Останні помилки в логах:"
sudo journalctl -u mimic -n 50 --no-pager | grep -iE "(error|exception|traceback|static_version)" | tail -10

# 4. Перевірка, чи файли існують
echo ""
echo "📁 4. Перевірка наявності JS файлів:"
ls -lh static/js/*.js 2>/dev/null

# 5. Перевірка доступності через curl
echo ""
echo "🌐 5. Тестую доступність JS файлів:"
for file in "main.min.js" "push.js" "chat.js"; do
    URL="https://mimiccash.com/static/js/$file"
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")
    SIZE=$(curl -s -o /dev/null -w "%{size_download}" "$URL")
    echo "  $file: HTTP $STATUS, Size: $SIZE bytes"
done

echo ""
echo "✅ Діагностика завершена!"
