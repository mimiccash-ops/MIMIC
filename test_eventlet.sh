#!/bin/bash
# Test eventlet worker

echo "🧪 Тестую eventlet worker..."
echo ""

cd /var/www/mimic || exit 1
source venv/bin/activate

# 1. Перевірити останні помилки
echo "📋 Останні помилки з error.log:"
tail -20 logs/error.log 2>/dev/null | grep -i "error\|exception\|traceback" || echo "  (немає помилок у хвості)"
echo ""

# 2. Спробувати запустити gunicorn з eventlet вручну
echo "🧪 Тестовий запуск gunicorn з eventlet (5 секунд):"
timeout 5 gunicorn --worker-class eventlet --workers 1 --bind 127.0.0.1:8003 --timeout 5 --log-level debug app:app 2>&1 | head -50 || echo ""
echo ""

# 3. Перевірити версію eventlet
echo "📋 Версія eventlet:"
python3 -c "import eventlet; print(f'eventlet {eventlet.__version__}')" 2>&1
echo ""

# 4. Перевірити, чи eventlet може імпортуватися
echo "📋 Перевірка імпорту eventlet:"
python3 -c "import eventlet; eventlet.monkey_patch(); print('✅ eventlet працює')" 2>&1 || echo "  ❌ Помилка eventlet!"
echo ""

echo "✅ Діагностика завершена!"
