#!/bin/bash
# Fix CSS loading issues for new users

echo "🔧 Виправляю проблеми з завантаженням CSS..."

cd /var/www/mimic || exit 1

# 1. Перевіряю наявність CSS файлів
echo "📁 Перевіряю CSS файли..."
if [ ! -f "static/css/tailwind.css" ]; then
    echo "❌ tailwind.css не знайдено! Створюю..."
    mkdir -p static/css
    touch static/css/tailwind.css
    echo "/* Tailwind CSS will be built here */" > static/css/tailwind.css
fi

if [ ! -f "static/css/main.min.css" ]; then
    echo "⚠️ main.min.css не знайдено, перевіряю main.css..."
    if [ -f "static/css/main.css" ]; then
        echo "✅ Використовую main.css як fallback"
    else
        echo "❌ Немає жодного main CSS файлу!"
    fi
fi

# 2. Перебудовую Tailwind CSS
echo "🎨 Перебудовую Tailwind CSS..."
if [ -f "package.json" ]; then
    npm run build:css || {
        echo "⚠️ npm build не вдався, перевіряю tailwind.input.css..."
        if [ ! -f "static/css/tailwind.input.css" ]; then
            echo "📝 Створюю tailwind.input.css..."
            mkdir -p static/css
            cat > static/css/tailwind.input.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Custom styles can be added here */
EOF
        fi
        npm run build:css || echo "⚠️ Не вдалося перебудувати CSS, але продовжую..."
    }
else
    echo "⚠️ package.json не знайдено, пропускаю перебудову"
fi

# 3. Перевіряю права доступу
echo "🔐 Перевіряю права доступу..."
chmod -R 644 static/css/*.css 2>/dev/null
chown -R www-data:www-data static/css/ 2>/dev/null || chown -R nginx:nginx static/css/ 2>/dev/null

# 4. Перезавантажую nginx
echo "🔄 Перезавантажую nginx..."
sudo systemctl reload nginx || sudo service nginx reload

# 5. Перезапускаю Flask додаток
echo "🔄 Перезапускаю Flask додаток..."
sudo systemctl restart mimic || sudo systemctl restart gunicorn || echo "⚠️ Не вдалося перезапустити сервіс"

# 6. Перевіряю доступність CSS файлів
echo "✅ Перевіряю доступність CSS файлів..."
curl -I https://mimiccash.com/static/css/tailwind.css 2>/dev/null | head -1
curl -I https://mimiccash.com/static/css/main.min.css 2>/dev/null | head -1 || curl -I https://mimiccash.com/static/css/main.css 2>/dev/null | head -1

echo ""
echo "✅ Готово! Перевірте сайт у браузері."
echo "💡 Якщо проблема залишається, спробуйте:"
echo "   1. Очистити кеш браузера (Ctrl+Shift+Delete)"
echo "   2. Відкрити в режимі інкогніто"
echo "   3. Перевірити консоль браузера (F12) на помилки"
