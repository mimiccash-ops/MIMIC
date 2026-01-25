#!/bin/bash
# Check why mimic service is failing

echo "🔍 Перевіряю помилки сервісу mimic..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірити логи systemd
echo "📋 Останні логи systemd:"
sudo journalctl -u mimic -n 50 --no-pager | tail -30
echo ""

# 2. Перевірити логи помилок додатку
echo "📋 Останні помилки з error.log:"
if [ -f logs/error.log ]; then
    tail -30 logs/error.log
else
    echo "  ⚠️ Файл logs/error.log не знайдено"
fi
echo ""

# 3. Перевірити Python синтаксис
echo "📋 Перевірка Python синтаксису:"
if python3 -c "from app import app; print('✅ Python синтаксис OK')" 2>&1; then
    echo "  ✅ Python синтаксис OK"
else
    echo "  ❌ Помилка Python синтаксису!"
fi
echo ""

# 4. Спробувати запустити gunicorn вручну
echo "📋 Тестовий запуск gunicorn:"
cd /var/www/mimic
source venv/bin/activate
timeout 5 gunicorn --worker-class eventlet --workers 1 --bind 127.0.0.1:8001 --timeout 5 app:app 2>&1 | head -20 || echo "  ⚠️ Gunicorn не запустився (це нормально для тесту)"
echo ""

# 5. Перевірити залежності
echo "📋 Перевірка залежностей:"
python3 -c "import flask, gunicorn, eventlet; print('✅ Основні залежності OK')" 2>&1 || echo "  ❌ Проблема з залежностями!"
echo ""

echo "✅ Діагностика завершена!"
