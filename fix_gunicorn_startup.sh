#!/bin/bash
# Fix gunicorn startup issue

echo "🔧 Діагностика проблеми з gunicorn..."
echo ""

cd /var/www/mimic || exit 1
source venv/bin/activate

# 1. Перевірити логи помилок
echo "📋 Останні помилки з error.log:"
if [ -f logs/error.log ]; then
    tail -30 logs/error.log | grep -A 10 -B 5 -i "error\|exception\|traceback" || tail -30 logs/error.log
else
    echo "  ⚠️ Файл logs/error.log не знайдено"
fi
echo ""

# 2. Спробувати запустити gunicorn з мінімальною конфігурацією
echo "🧪 Тестовий запуск gunicorn (мінімальна конфігурація):"
timeout 3 gunicorn --bind 127.0.0.1:8001 --timeout 3 --log-level info app:app 2>&1 | head -30 || echo ""
echo ""

# 3. Спробувати без eventlet
echo "🧪 Тестовий запуск gunicorn (без eventlet):"
timeout 3 gunicorn --workers 1 --bind 127.0.0.1:8002 --timeout 3 --log-level info app:app 2>&1 | head -30 || echo ""
echo ""

# 4. Перевірити, чи можна імпортувати app
echo "📋 Перевірка імпорту app:"
python3 -c "from app import app; print('✅ app імпортується успішно')" 2>&1 || echo "  ❌ Помилка імпорту app!"
echo ""

# 5. Перевірити, чи є проблеми з Flask
echo "📋 Перевірка Flask:"
python3 -c "from flask import Flask; print('✅ Flask доступний')" 2>&1 || echo "  ❌ Flask не доступний!"
echo ""

echo "✅ Діагностика завершена!"
