#!/bin/bash
# Test gunicorn startup to see exact error

echo "🧪 Тестую запуск gunicorn..."
echo ""

cd /var/www/mimic || exit 1
source venv/bin/activate

# 1. Перевірити логи помилок
echo "📋 Останні помилки з error.log:"
if [ -f logs/error.log ]; then
    tail -30 logs/error.log
else
    echo "  ⚠️ Файл logs/error.log не знайдено"
fi
echo ""

# 2. Спробувати запустити gunicorn вручну
echo "🧪 Тестовий запуск gunicorn (5 секунд):"
timeout 5 gunicorn --worker-class eventlet --workers 1 --bind 127.0.0.1:8001 --timeout 5 --log-level debug app:app 2>&1 | head -50 || echo ""
echo ""

# 3. Перевірити, чи eventlet доступний
echo "📋 Перевірка eventlet:"
python3 -c "import eventlet; print(f'✅ eventlet версія: {eventlet.__version__}')" 2>&1 || echo "  ❌ eventlet не встановлено!"
echo ""

# 4. Перевірити, чи gunicorn доступний
echo "📋 Перевірка gunicorn:"
python3 -c "import gunicorn; print(f'✅ gunicorn доступний')" 2>&1 || echo "  ❌ gunicorn не встановлено!"
echo ""

# 5. Перевірити, чи можна імпортувати app
echo "📋 Перевірка імпорту app:"
python3 -c "from app import app; print('✅ app імпортується успішно')" 2>&1 || echo "  ❌ Помилка імпорту app!"
echo ""

echo "✅ Діагностика завершена!"
