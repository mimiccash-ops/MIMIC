#!/bin/bash
# Verify that the site is working after fixes

echo "🔍 Перевіряю роботу сайту..."

# 1. Перевіряю чи працює gunicorn
echo ""
echo "📊 Статус mimic сервісу:"
sudo systemctl status mimic --no-pager -l | head -10

# 2. Перевіряю чи слухає порт 8000
echo ""
echo "🌐 Перевіряю порт 8000:"
if netstat -tlnp 2>/dev/null | grep -q ":8000" || ss -tlnp 2>/dev/null | grep -q ":8000"; then
    echo "✅ Порт 8000 відкритий і слухає"
    netstat -tlnp 2>/dev/null | grep ":8000" || ss -tlnp 2>/dev/null | grep ":8000"
else
    echo "❌ Порт 8000 не відкритий!"
fi

# 3. Перевіряю локальний доступ
echo ""
echo "🧪 Тестую локальний доступ:"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://127.0.0.1:8000/health 2>&1 || echo "❌ Не вдалося підключитися"

# 4. Перевіряю через nginx
echo ""
echo "🌐 Тестую через nginx:"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" https://mimiccash.com/health 2>&1 || echo "⚠️ Перевірте вручну"

# 5. Перевіряю CSS файли
echo ""
echo "🎨 Перевіряю CSS файли:"
curl -s -o /dev/null -w "tailwind.css: %{http_code}\n" https://mimiccash.com/static/css/tailwind.css 2>&1
curl -s -o /dev/null -w "main.min.css: %{http_code}\n" https://mimiccash.com/static/css/main.min.css 2>&1

# 6. Перевіряю останні помилки
echo ""
echo "📋 Останні 10 рядків логів (якщо є помилки):"
sudo journalctl -u mimic -n 10 --no-pager | grep -iE "(error|exception|traceback)" | tail -5 || echo "✅ Помилок не знайдено"

echo ""
echo "✅ Перевірка завершена!"
echo "💡 Відкрийте сайт у браузері та перевірте, чи завантажуються стилі"
