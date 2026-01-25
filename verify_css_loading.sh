#!/bin/bash
# Verify CSS loading with versioning

echo "🔍 Перевіряю завантаження CSS з версіонуванням..."

# 1. Перевіряю HTML - чи є версіонування
echo ""
echo "📄 Перевіряю HTML (версіонування CSS):"
TAILWIND_URL=$(curl -s "https://mimiccash.com/" | grep -o 'href="[^"]*tailwind\.css[^"]*"' | head -1)
if [ -n "$TAILWIND_URL" ]; then
    echo "✅ Знайдено: $TAILWIND_URL"
    if echo "$TAILWIND_URL" | grep -q "?v="; then
        echo "✅ Версіонування працює!"
    else
        echo "⚠️ Версіонування не знайдено в URL"
    fi
else
    echo "❌ Не знайдено tailwind.css в HTML"
fi

# 2. Перевіряю доступність CSS файлів
echo ""
echo "🌐 Перевіряю доступність CSS файлів:"
curl -s -o /dev/null -w "tailwind.css: HTTP %{http_code}\n" "https://mimiccash.com/static/css/tailwind.css" 2>&1
curl -s -o /dev/null -w "main.min.css: HTTP %{http_code}\n" "https://mimiccash.com/static/css/main.min.css" 2>&1
curl -s -o /dev/null -w "chat.css: HTTP %{http_code}\n" "https://mimiccash.com/static/css/chat.css" 2>&1

# 3. Перевіряю заголовки кешування
echo ""
echo "📋 Заголовки кешування для tailwind.css:"
curl -s -I "https://mimiccash.com/static/css/tailwind.css?v=test" 2>&1 | grep -iE "(cache-control|expires)" | head -2

# 4. Перевіряю розмір CSS файлів
echo ""
echo "📊 Розміри CSS файлів:"
ls -lh static/css/*.css 2>/dev/null | awk '{print $9, $5}'

# 5. Перевіряю, чи працює версіонування через Python
echo ""
echo "🐍 Тестую версіонування через Python:"
cd /var/www/mimic
source venv/bin/activate
python3 test_versioning.py 2>&1 | grep -E "(tailwind|main|chat|Testing)" | head -5

echo ""
echo "✅ Перевірка завершена!"
echo "💡 Якщо версіонування працює, URL має містити ?v=..."
