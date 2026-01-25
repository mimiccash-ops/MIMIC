#!/bin/bash
# Final fix for JavaScript syntax error - fix missing closing quote after success value

echo "🔧 Виправляю синтаксичну помилку в main.min.js..."
echo ""

cd /var/www/mimic || exit 1

# 1. Створити резервну копію
echo "💾 Створюю резервну копію..."
cp static/js/main.min.js static/js/main.min.js.backup3
echo "  ✅ Резервна копія створена"

# 2. Виправити помилку - додати закриваючу лапку після success
echo ""
echo "🔧 Виправляю помилку..."
# Знайти і замінити: /v7,notification: на /v7',notification:
# Але спочатку перевіримо, чи вже є лапка
if grep -q "/v7',notification:" static/js/main.min.js; then
    echo "  ℹ️ Лапка вже додана, перевіряю інші місця..."
else
    # Замінити /v7,notification: на /v7',notification:
    sed -i "s|/v7,notification:|/v7',notification:|g" static/js/main.min.js
    echo "  ✅ Додано закриваючу лапку після success"
fi

# 3. Перевірка синтаксису через node
echo ""
echo "📋 Перевірка синтаксису..."
if command -v node &> /dev/null; then
    if node -c static/js/main.min.js 2>&1; then
        echo "  ✅ Синтаксис виправлено!"
    else
        echo "  ❌ Помилка залишається, спробую інший підхід..."
        # Спробувати знайти точне місце помилки
        echo "  🔍 Шукаю точне місце помилки..."
        # Знайти рядок з soundData
        grep -o "soundData.*notification" static/js/main.min.js | head -c 200
        echo ""
        echo "  💡 Спробую замінити всі місця, де може бути проблема..."
        # Замінити всі випадки, де після success немає лапки перед notification
        sed -i "s|success:'\([^']*\)',notification:|success:'\1',notification:|g" static/js/main.min.js
        sed -i "s|success:'\([^']*\)+notification:|success:'\1',notification:|g" static/js/main.min.js
        sed -i "s|success:'\([^']*\)notification:|success:'\1',notification:|g" static/js/main.min.js
        
        # Перевірити знову
        if node -c static/js/main.min.js 2>&1; then
            echo "  ✅ Синтаксис виправлено другим способом!"
        else
            echo "  ❌ Помилка залишається, відновлюю з резервної копії"
            cp static/js/main.min.js.backup3 static/js/main.min.js
            exit 1
        fi
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
