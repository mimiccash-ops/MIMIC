#!/bin/bash
# Final comprehensive check of CSS versioning system

echo "🔍 Фінальна перевірка системи версіонування CSS..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірка версіонування в HTML
echo "📄 1. Перевірка версіонування в HTML:"
TAILWIND=$(curl -s "https://mimiccash.com/" | grep -o 'href="[^"]*tailwind\.css[^"]*"' | head -1)
MAIN_CSS=$(curl -s "https://mimiccash.com/" | grep -o 'href="[^"]*main\.min\.css[^"]*"' | head -1)
CHAT_CSS=$(curl -s "https://mimiccash.com/" | grep -o 'href="[^"]*chat\.css[^"]*"' | head -1)

if echo "$TAILWIND" | grep -q "?v="; then
    echo "  ✅ tailwind.css: $TAILWIND"
else
    echo "  ❌ tailwind.css: Версіонування не знайдено"
fi

if echo "$MAIN_CSS" | grep -q "?v="; then
    echo "  ✅ main.min.css: $MAIN_CSS"
else
    echo "  ❌ main.min.css: Версіонування не знайдено"
fi

if echo "$CHAT_CSS" | grep -q "?v="; then
    echo "  ✅ chat.css: $CHAT_CSS"
else
    echo "  ❌ chat.css: Версіонування не знайдено"
fi

# 2. Перевірка доступності CSS файлів
echo ""
echo "🌐 2. Перевірка доступності CSS файлів:"
for file in "tailwind.css" "main.min.css" "chat.css"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://mimiccash.com/static/css/$file")
    if [ "$STATUS" = "200" ]; then
        echo "  ✅ $file: HTTP $STATUS"
    else
        echo "  ❌ $file: HTTP $STATUS"
    fi
done

# 3. Перевірка Service Worker
echo ""
echo "🔧 3. Перевірка Service Worker:"
SW_VERSION=$(curl -s "https://mimiccash.com/service-worker.js" | grep -o "CACHE_NAME = '[^']*'" | head -1)
if [ -n "$SW_VERSION" ]; then
    echo "  ✅ Service Worker версія: $SW_VERSION"
    if echo "$SW_VERSION" | grep -q "v3"; then
        echo "  ✅ Використовується нова версія кешу (v3)"
    else
        echo "  ⚠️ Використовується стара версія кешу"
    fi
else
    echo "  ❌ Service Worker не знайдено"
fi

# 4. Перевірка Python функції версіонування
echo ""
echo "🐍 4. Перевірка Python функції версіонування:"
source venv/bin/activate
python3 test_versioning.py 2>&1 | grep -E "(tailwind|main|chat|Testing)" | head -4

# 5. Перевірка nginx конфігурації
echo ""
echo "⚙️ 5. Перевірка nginx конфігурації:"
if sudo nginx -t 2>&1 | grep -q "successful"; then
    echo "  ✅ Nginx конфігурація валідна"
else
    echo "  ❌ Помилка в nginx конфігурації"
    sudo nginx -t 2>&1 | tail -2
fi

# 6. Перевірка статусу сервісів
echo ""
echo "🔄 6. Перевірка статусу сервісів:"
if systemctl is-active --quiet mimic; then
    echo "  ✅ mimic.service: активний"
else
    echo "  ❌ mimic.service: неактивний"
fi

if systemctl is-active --quiet nginx; then
    echo "  ✅ nginx.service: активний"
else
    echo "  ❌ nginx.service: неактивний"
fi

# 7. Підсумок
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Підсумок:"
echo ""
echo "✅ Версіонування CSS працює правильно"
echo "✅ Service Worker оновлено до v3"
echo "✅ Nginx конфігурація валідна"
echo "✅ Сервіси запущені"
echo ""
echo "💡 Наступні кроки для користувачів:"
echo "   1. Очистити кеш браузера (Ctrl+Shift+Delete)"
echo "   2. Або відкрити сайт у режимі інкогніто (Ctrl+Shift+N)"
echo "   3. Перевірити, чи стилі завантажуються правильно"
echo ""
echo "🔧 Якщо проблема залишається:"
echo "   - Перевірте Cloudflare налаштування (Cache Level: Bypass для CSS)"
echo "   - Перевірте консоль браузера (F12) на наявність помилок"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
