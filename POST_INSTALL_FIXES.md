# 🔧 Виправлення проблем після встановлення

Після встановлення є кілька проблем, які потрібно виправити:

## ✅ Проблеми, які були виявлені:

1. **Sentry DSN помилка** - невалідний DSN в .env файлі
2. **Redis service** - сервіс не запускається
3. **Міграції** - не виконалися через помилку Sentry

## 🚀 Швидке виправлення

На вашому VPS виконайте:

```bash
cd /var/www/mimic
sudo chmod +x fix_installation_issues.sh
sudo ./fix_installation_issues.sh
```

## 📝 Ручне виправлення

### 1. Виправити Sentry DSN

```bash
cd /var/www/mimic
nano .env
```

Знайдіть рядок:
```
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

Замініть на (закоментуйте або видаліть):
```
# SENTRY_DSN=  # Optional: Add your Sentry DSN here
```

Або якщо у вас є реальний Sentry DSN, додайте його:
```
SENTRY_DSN=https://your-real-dsn@sentry.io/your-project-id
```

### 2. Виправити Redis

```bash
# Перевірити, чи Redis запущений
redis-cli ping

# Якщо не запущений, спробувати:
sudo systemctl start redis-server
# або
sudo systemctl start redis

# Перевірити статус
sudo systemctl status redis-server
# або
sudo systemctl status redis
```

### 3. Запустити міграції знову

```bash
cd /var/www/mimic
source venv/bin/activate
python migrations/migrate.py
```

## ⚙️ Налаштування конфігурації

### 1. Редагувати .env файл

```bash
nano /var/www/mimic/.env
```

**Обов'язкові налаштування:**
- `FLASK_SECRET_KEY` - вже згенеровано
- `DATABASE_URL` - вже налаштовано
- `REDIS_URL` - вже налаштовано
- `FLASK_ENV=production`
- `HTTPS_ENABLED=true`

**Опціональні:**
- `SENTRY_DSN` - тільки якщо використовуєте Sentry
- `TELEGRAM_BOT_TOKEN` - для Telegram бота
- `OPENAI_API_KEY` - для AI чат-бота

### 2. Редагувати config.ini

```bash
nano /var/www/mimic/config.ini
```

**Додати ваші API ключі:**
- `[MasterAccount]` - Binance API ключі
- `[Telegram]` - Telegram bot token
- `[Webhook]` - Webhook passphrase

## 🚀 Запуск сервісів

Після виправлення проблем:

```bash
# Запустити всі сервіси
sudo systemctl start mimic
sudo systemctl start mimic-worker
sudo systemctl start mimic-bot

# Перевірити статус
sudo systemctl status mimic
sudo systemctl status mimic-worker
sudo systemctl status mimic-bot

# Переглянути логи
sudo journalctl -u mimic -f
```

## ✅ Перевірка

```bash
# Перевірити, чи працює веб-сервер
curl http://localhost:8000

# Перевірити Redis
redis-cli ping
# Має повернути: PONG

# Перевірити базу даних
sudo -u postgres psql -d mimic_db -c "SELECT version();"
```

## 📊 База даних

**Збережіть ці дані:**
- User: `mimic_user`
- Database: `mimic_db`
- Password: `bZNOkq0dXC2kD03HLjlHTlp9P` (збережіть це!)

## 🔍 Логи

```bash
# Логи веб-сервера
sudo journalctl -u mimic -f

# Логи worker
sudo journalctl -u mimic-worker -f

# Логи бота
sudo journalctl -u mimic-bot -f

# Логи додатку
tail -f /var/www/mimic/logs/app.log
```

## ⚠️ Якщо щось не працює

1. **Сервіс не запускається:**
   ```bash
   sudo systemctl status mimic
   sudo journalctl -u mimic -n 50
   ```

2. **Помилки бази даних:**
   ```bash
   sudo systemctl status postgresql
   sudo -u postgres psql -d mimic_db
   ```

3. **Помилки Redis:**
   ```bash
   redis-cli ping
   sudo systemctl status redis-server
   ```

4. **Проблеми з правами:**
   ```bash
   sudo chown -R mimic:mimic /var/www/mimic
   sudo chmod 600 /var/www/mimic/.env
   ```

## 🎯 Наступні кроки

1. ✅ Виправити Sentry DSN
2. ✅ Запустити Redis
3. ✅ Запустити міграції
4. ✅ Налаштувати .env та config.ini
5. ✅ Запустити сервіси
6. ⚙️ Налаштувати Nginx (див. LINUX_DEPLOYMENT.md)
7. 🔒 Налаштувати SSL сертифікат
