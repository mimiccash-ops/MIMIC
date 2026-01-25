#!/bin/bash
# Check if JavaScript files are loading correctly

echo "🔍 Перевіряю завантаження JavaScript файлів..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірка наявності файлів
echo "📁 Перевірка наявності файлів:"
for file in "static/js/main.min.js" "static/js/push.js" "static/js/chat.js"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file існує"
    else
        echo "  ❌ $file не знайдено"
    fi
done

# 2. Перевірка HTML - чи правильно завантажуються скрипти
echo ""
echo "📄 Перевірка HTML (завантаження скриптів):"
MAIN_JS=$(curl -s "https://mimiccash.com/" | grep -o 'src="[^"]*main\.min\.js[^"]*"' | head -1)
PUSH_JS=$(curl -s "https://mimiccash.com/" | grep -o 'src="[^"]*push\.js[^"]*"' | head -1)
CHAT_JS=$(curl -s "https://mimiccash.com/" | grep -o 'src="[^"]*chat\.js[^"]*"' | head -1)

if [ -n "$MAIN_JS" ]; then
    echo "  ✅ main.min.js: $MAIN_JS"
    if echo "$MAIN_JS" | grep -q "?v="; then
        echo "    ✅ Версіонування працює"
    else
        echo "    ⚠️ Версіонування не знайдено"
    fi
else
    echo "  ❌ main.min.js не знайдено в HTML"
fi

if [ -n "$PUSH_JS" ]; then
    echo "  ✅ push.js: $PUSH_JS"
else
    echo "  ❌ push.js не знайдено в HTML"
fi

if [ -n "$CHAT_JS" ]; then
    echo "  ✅ chat.js: $CHAT_JS"
else
    echo "  ❌ chat.js не знайдено в HTML"
fi

# 3. Перевірка доступності JS файлів
echo ""
echo "🌐 Перевірка доступності JS файлів:"
for file in "main.min.js" "push.js" "chat.js"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://mimiccash.com/static/js/$file")
    if [ "$STATUS" = "200" ]; then
        echo "  ✅ $file: HTTP $STATUS"
    else
        echo "  ❌ $file: HTTP $STATUS"
    fi
done

# 4. Перевірка розмірів файлів
echo ""
echo "📊 Розміри JS файлів:"
ls -lh static/js/*.js 2>/dev/null | awk '{print $9, $5}'

echo ""
echo "✅ Перевірка завершена!"
