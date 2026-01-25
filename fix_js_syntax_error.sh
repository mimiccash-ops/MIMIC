#!/bin/bash
# Fix JavaScript syntax error in main.min.js
# The issue is missing comma between 'success' and 'notification' in soundData

echo "🔧 Виправляю синтаксичну помилку в main.min.js..."
echo ""

cd /var/www/mimic || exit 1

# 1. Створити резервну копію
echo "💾 Створюю резервну копію..."
cp static/js/main.min.js static/js/main.min.js.backup
echo "  ✅ Резервна копія створена"

# 2. Виправити помилку - додати кому між success і notification
echo ""
echo "🔧 Виправляю помилку..."
# Знайти і замінити: success:'...' notification: на success:'...',notification:
sed -i "s/success:'UklGRjIFAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQ4FAAB\/f39\/f39\/f39\/gICAgICAgICAgYGBgYGCgoKCg4ODg4SEhISFhYWGhoaHh4eIiIiJiYmKioqLi4uMjIyNjY2Ojo6Pj4+QkJCRkZGSkpKTk5OUlJSVlZWWlpaXl5eYmJiZmZmampqbm5ucnJydnZ2enp6fn5+goKChoaGioqKjo6OkpKSlpaWmpqanp6eoqKipqamqqqqrq6usrKytra2urq6vr6+wsLCxsbGysrKzs7O0tLS1tbW2tra3t7e4uLi5ubm6urq7u7u8vLy9vb2+vr6\/v7\/AwMDBwcHCwsLDw8PExMTFxcXGxsbHx8fIyMjJycnKysrLy8vMzMzNzc3Ozs7Pz8\/Q0NDR0dHS0tLT09PU1NTV1dXW1tbX19fY2NjZ2dna2trb29vc3Nzd3d3e3t7f39\/g4ODh4eHi4uLj4+Pk5OTl5eXm5ubn5+fo6Ojp6enq6urr6+vs7Ozt7e3u7u7v7+\/w8PDx8fLy8vPz9PT09fX29vb39\/f4+Pj5+fn6+vr7+\/v8\/Pz9\/f3+\/v7 notification:/success:'UklGRjIFAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQ4FAAB\/f39\/f39\/f39\/gICAgICAgICAgYGBgYGCgoKCg4ODg4SEhISFhYWGhoaHh4eIiIiJiYmKioqLi4uMjIyNjY2Ojo6Pj4+QkJCRkZGSkpKTk5OUlJSVlZWWlpaXl5eYmJiZmZmampqbm5ucnJydnZ2enp6fn5+goKChoaGioqKjo6OkpKSlpaWmpqanp6eoqKipqamqqqqrq6usrKytra2urq6vr6+wsLCxsbGysrKzs7O0tLS1tbW2tra3t7e4uLi5ubm6urq7u7u8vLy9vb2+vr6\/v7\/AwMDBwcHCwsLDw8PExMTFxcXGxsbHx8fIyMjJycnKysrLy8vMzMzNzc3Ozs7Pz8\/Q0NDR0dHS0tLT09PU1NTV1dXW1tbX19fY2NjZ2dna2trb29vc3Nzd3d3e3t7f39\/g4ODh4eHi4uLj4+Pk5OTl5eXm5ubn5+fo6Ojp6enq6urr6+vs7Ozt7e3u7u7v7+\/w8PDx8fLy8vPz9PT09fX29vb39\/f4+Pj5+fn6+vr7+\/v8\/Pz9\/f3+\/v7',notification:/g" static/js/main.min.js

# 3. Перевірка синтаксису через node (якщо доступний)
echo ""
echo "📋 Перевірка синтаксису..."
if command -v node &> /dev/null; then
    if node -c static/js/main.min.js 2>&1; then
        echo "  ✅ Синтаксис виправлено!"
    else
        echo "  ❌ Помилка залишається, відновлюю з резервної копії"
        cp static/js/main.min.js.backup static/js/main.min.js
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
