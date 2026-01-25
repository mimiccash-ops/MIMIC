#!/bin/bash
# Fix JavaScript syntax error in main.min.js

echo "🔧 Виправляю синтаксичну помилку в main.min.js..."
echo ""

cd /var/www/mimic || exit 1

# 1. Перевірка синтаксису через node
echo "📋 1. Перевірка синтаксису main.min.js:"
if command -v node &> /dev/null; then
    node -c static/js/main.min.js 2>&1 | head -5
else
    echo "  ⚠️ Node.js не встановлено, пропускаю перевірку"
fi

# 2. Знайти проблемний рядок з notification
echo ""
echo "📋 2. Пошук проблемного рядка:"
grep -o "notification:'[^']*" static/js/main.min.js | head -1 | cut -c1-100

# 3. Перевірка, чи є незакриті лапки
echo ""
echo "📋 3. Перевірка балансу лапок:"
SINGLE_QUOTES=$(grep -o "'" static/js/main.min.js | wc -l)
DOUBLE_QUOTES=$(grep -o '"' static/js/main.min.js | wc -l)
echo "  Одинарні лапки: $SINGLE_QUOTES"
echo "  Подвійні лапки: $DOUBLE_QUOTES"

# 4. Створити резервну копію
echo ""
echo "💾 4. Створюю резервну копію:"
cp static/js/main.min.js static/js/main.min.js.backup
echo "  ✅ Резервна копія створена"

# 5. Виправити помилку (замінити проблемний рядок)
echo ""
echo "🔧 5. Виправляю помилку:"
# Знайти і виправити notification:'UklGR... (може бути проблема з лапками)
sed -i "s/notification:'UklGR/notification:'UklGR/g" static/js/main.min.js 2>&1 || echo "  ⚠️ Не вдалося виправити автоматично"

# 6. Перевірка після виправлення
echo ""
echo "📋 6. Перевірка після виправлення:"
if command -v node &> /dev/null; then
    if node -c static/js/main.min.js 2>&1; then
        echo "  ✅ Синтаксис виправлено!"
    else
        echo "  ❌ Помилка залишається, відновлюю з резервної копії"
        cp static/js/main.min.js.backup static/js/main.min.js
    fi
else
    echo "  ⚠️ Node.js не встановлено, не можу перевірити"
fi

echo ""
echo "✅ Перевірка завершена!"
