#!/bin/bash
# Final fix for JavaScript syntax error - add closing quote after success value

echo "🔧 Виправляю синтаксичну помилку в main.min.js..."
echo ""

cd /var/www/mimic || exit 1

# 1. Створити резервну копію
echo "💾 Створюю резервну копію..."
cp static/js/main.min.js static/js/main.min.js.backup2
echo "  ✅ Резервна копія створена"

# 2. Виправити помилку - додати закриваючу лапку після success
echo ""
echo "🔧 Виправляю помилку..."
# Знайти і замінити: /f39/g...+/v7,notification: на /f39/g...+/v7',notification:
# Використовуємо більш простий підхід - замінити ",notification:" на "',notification:"
sed -i "s/,notification:/',notification:/g" static/js/main.min.js

# 3. Перевірка синтаксису через node
echo ""
echo "📋 Перевірка синтаксису..."
if command -v node &> /dev/null; then
    if node -c static/js/main.min.js 2>&1; then
        echo "  ✅ Синтаксис виправлено!"
    else
        echo "  ❌ Помилка залишається, відновлюю з резервної копії"
        cp static/js/main.min.js.backup2 static/js/main.min.js
        exit 1
    fi
else
    echo "  ⚠️ Node.js не встановлено, не можу перевірити"
fi

# 4. Перезапуск сервісу
echo ""
echo "🔄 Перезапускаю сервіс..."
sudo systemctl restart mimic
sleep 2

# 5. Перевірка статусу
echo ""
echo "📋 Статус сервісу:"
sudo systemctl status mimic --no-pager -l | head -10

echo ""
echo "✅ Готово! Перевірте сайт у браузері."
