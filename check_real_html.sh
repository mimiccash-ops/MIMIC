#!/bin/bash
# Check real HTML for scripts

echo "🔍 Перевіряю реальний HTML на наявність скриптів..."
echo ""

# 1. Перевірка всіх script тегів
echo "📄 Всі script теги в HTML:"
curl -s "https://mimiccash.com/" | grep -i "<script" | head -20

# 2. Перевірка конкретно наших скриптів
echo ""
echo "📄 Перевірка наших JS файлів:"
curl -s "https://mimiccash.com/" | grep -E "(main\.min\.js|push\.js|chat\.js)" | head -10

# 3. Перевірка, чи є версіонування
echo ""
echo "📄 Перевірка версіонування:"
curl -s "https://mimiccash.com/" | grep -E "\?v=" | head -10

# 4. Зберегти HTML для детального аналізу
echo ""
echo "💾 Зберігаю HTML для аналізу..."
curl -s "https://mimiccash.com/" > /tmp/mimic_html.html
echo "HTML збережено в /tmp/mimic_html.html"
echo "Розмір: $(wc -l < /tmp/mimic_html.html) рядків"

# 5. Перевірка, чи є скрипти в кінці HTML (перед </body>)
echo ""
echo "📄 Останні 30 рядків HTML (де мають бути скрипти):"
tail -30 /tmp/mimic_html.html

echo ""
echo "✅ Перевірка завершена!"
