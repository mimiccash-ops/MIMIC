#!/bin/bash
# Fix git pull conflicts by stashing local changes

echo "🔄 Виправляю конфлікти git pull..."

cd /var/www/mimic || exit 1

# 1. Stash локальні зміни
echo "📦 Зберігаю локальні зміни..."
git stash push -m "Stash before pull - service-worker.js updates"

# 2. Pull останні зміни
echo "⬇️ Завантажую останні зміни..."
git pull

# 3. Застосовую зміни знову (якщо потрібно)
echo "🔄 Перевіряю, чи потрібно застосувати зміни..."
if git stash list | grep -q "Stash before pull"; then
    echo "✅ Зміни збережено в stash"
    echo "💡 Якщо потрібно застосувати зміни знову, виконайте: git stash pop"
fi

echo ""
echo "✅ Готово! Тепер можна перезапустити сервіси:"
echo "   sudo systemctl restart mimic"
echo "   sudo systemctl reload nginx"
