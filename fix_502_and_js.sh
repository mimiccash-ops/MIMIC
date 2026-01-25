#!/bin/bash
# Fix 502 error and JavaScript issues

echo "🔧 Виправляю 502 помилку та проблеми з JavaScript..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірка статусу сервісу
echo "📋 1. Перевірка статусу сервісу:"
sudo systemctl status mimic --no-pager -l | head -20

# 2. Перевірка помилок
echo ""
echo "📋 2. Останні помилки:"
sudo journalctl -u mimic -n 50 --no-pager | grep -iE "(error|exception|traceback)" | tail -10

# 3. Перевірка синтаксису Python
echo ""
echo "📋 3. Перевірка синтаксису app.py:"
python3 -c "from app import app; print('✅ app.py OK')" 2>&1 | head -5

# 4. Перезапуск сервісу
echo ""
echo "🔄 4. Перезапуск сервісу:"
sudo systemctl restart mimic
sleep 3

# 5. Перевірка статусу після перезапуску
echo ""
echo "📋 5. Статус після перезапуску:"
sudo systemctl status mimic --no-pager -l | head -15

# 6. Перевірка доступності
echo ""
echo "🌐 6. Тестую доступність:"
curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" "http://127.0.0.1:8000/health" 2>&1

echo ""
echo "✅ Перевірка завершена!"
