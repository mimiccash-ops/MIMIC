#!/bin/bash
# Fix 502 Bad Gateway error

echo "🔧 Виправляю помилку 502 Bad Gateway..."

cd /var/www/mimic || exit 1

# 1. Перевіряю синтаксис Python
echo "📝 Перевіряю синтаксис app.py..."
python3 -m py_compile app.py 2>&1 | head -20
if [ $? -ne 0 ]; then
    echo "❌ Синтаксична помилка в app.py!"
    exit 1
fi
echo "✅ Синтаксис правильний"

# 2. Перевіряю чи є venv
if [ ! -d "venv" ]; then
    echo "❌ venv не знайдено!"
    exit 1
fi

# 3. Перевіряю чи працює gunicorn
echo "🔍 Перевіряю чи працює gunicorn..."
if pgrep -f "gunicorn.*app:app" > /dev/null; then
    echo "⚠️ Gunicorn вже запущений, зупиняю..."
    sudo systemctl stop mimic
    sleep 2
fi

# 4. Перевіряю чи порт 8000 вільний
echo "🔍 Перевіряю порт 8000..."
if lsof -i :8000 2>/dev/null | grep -q LISTEN; then
    echo "⚠️ Порт 8000 зайнятий, звільняю..."
    sudo fuser -k 8000/tcp 2>/dev/null
    sleep 2
fi

# 5. Спробувати запустити вручну для перевірки помилок
echo "🧪 Тестовий запуск gunicorn..."
source venv/bin/activate
timeout 10 python3 -c "
import sys
sys.path.insert(0, '/var/www/mimic')
try:
    from app import app
    print('✅ app.py імпортується успішно')
except Exception as e:
    print(f'❌ Помилка імпорту: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
" 2>&1

if [ $? -ne 0 ]; then
    echo "❌ Помилка імпорту app.py!"
    echo "📋 Детальні логи:"
    python3 -c "
import sys
sys.path.insert(0, '/var/www/mimic')
from app import app
" 2>&1 | head -50
    exit 1
fi

# 6. Перезапускаю сервіс
echo "🔄 Перезапускаю mimic сервіс..."
sudo systemctl restart mimic
sleep 3

# 7. Перевіряю статус
echo "📊 Статус сервісу:"
sudo systemctl status mimic --no-pager -l | head -15

# 8. Перевіряю логи
echo ""
echo "📋 Останні помилки:"
sudo journalctl -u mimic -n 30 --no-pager | grep -iE "(error|exception|traceback|failed)" | tail -10

# 9. Перевіряю чи слухає порт
echo ""
echo "🌐 Перевіряю порт 8000:"
if netstat -tlnp 2>/dev/null | grep -q ":8000" || ss -tlnp 2>/dev/null | grep -q ":8000"; then
    echo "✅ Порт 8000 відкритий"
else
    echo "❌ Порт 8000 не відкритий!"
    echo "📋 Останні 20 рядків логів:"
    sudo journalctl -u mimic -n 20 --no-pager
fi

echo ""
echo "✅ Діагностика завершена"
