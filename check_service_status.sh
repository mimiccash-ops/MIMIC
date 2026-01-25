#!/bin/bash
# Check service status and logs after restart

echo "🔍 Перевіряю статус сервісів..."

# 1. Перевіряю статус mimic сервісу
echo ""
echo "📊 Статус mimic сервісу:"
sudo systemctl status mimic --no-pager -l | head -20

# 2. Перевіряю останні логи
echo ""
echo "📋 Останні 50 рядків логів mimic:"
sudo journalctl -u mimic -n 50 --no-pager | tail -50

# 3. Перевіряю помилки
echo ""
echo "❌ Останні помилки:"
sudo journalctl -u mimic -n 100 --no-pager | grep -iE "(error|exception|traceback|failed)" | tail -20

# 4. Перевіряю чи працює процес
echo ""
echo "🔍 Процеси gunicorn/flask:"
ps aux | grep -E "(gunicorn|flask|python.*app)" | grep -v grep

# 5. Перевіряю порти
echo ""
echo "🌐 Відкриті порти:"
sudo netstat -tlnp | grep -E "(5000|8000|8080)" || ss -tlnp | grep -E "(5000|8000|8080)"

echo ""
echo "✅ Перевірка завершена"
