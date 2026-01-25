#!/bin/bash
# Final fix for security.py indentation and clear Python cache

echo "🔧 Фінальне виправлення security.py та очищення кешу..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірити поточний стан файлу
echo "📋 Поточний стан (рядки 628-635):"
sed -n '628,635p' security.py
echo ""

# 2. Виправити відступи правильно
echo "🔧 Виправляю відступи..."
# Рядок 630 має мати 8 пробілів (як рядок 631)
sed -i '630s/^[[:space:]]*/        /' security.py

# 3. Перевірити результат
echo "📋 Після виправлення (рядки 628-635):"
sed -n '628,635p' security.py
echo ""

# 4. Очистити Python кеш
echo "🧹 Очищаю Python кеш..."
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
echo "  ✅ Кеш очищено"
echo ""

# 5. Перевірити Python синтаксис
echo "📋 Перевірка Python синтаксису:"
if python3 -c "from app import app; print('✅ OK')" 2>&1 | grep -q "OK"; then
    echo "  ✅ Синтаксис виправлено!"
else
    echo "  ❌ Помилка залишається!"
    python3 -c "from app import app; print('OK')" 2>&1 | tail -5
    exit 1
fi
echo ""

# 6. Перевірити, чи файл на сервері правильний
echo "📋 Перевірка відступів (hex dump рядка 630):"
sed -n '630p' security.py | od -c | head -1
echo ""

echo "✅ Готово! Тепер можна перезапустити сервіс:"
echo "   sudo systemctl restart mimic"
