# 🔧 Швидке виправлення на VPS

## Проблема: Git ownership та відсутні файли

Виконайте ці команди по черзі:

```bash
# 1. Виправити права Git
sudo git config --global --add safe.directory /var/www/mimic

# 2. Оновити код з GitHub
cd /var/www/mimic
sudo git pull

# 3. Виправити права власності файлів
sudo chown -R mimic:mimic /var/www/mimic

# 4. Запустити скрипт виправлення
sudo chmod +x fix_installation_issues.sh
sudo ./fix_installation_issues.sh
```

## Альтернатива: Виправити вручну

Якщо скрипт не працює, виконайте вручну:

### 1. Виправити Sentry DSN

```bash
cd /var/www/mimic
sudo nano .env
```

Знайдіть рядок з `SENTRY_DSN` і закоментуйте його:
```
# SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

Або видаліть рядок повністю.

### 2. Запустити Redis

```bash
# Спробувати різні варіанти назви сервісу
sudo systemctl start redis-server || sudo systemctl start redis || sudo service redis start

# Перевірити
redis-cli ping
```

### 3. Запустити міграції

```bash
cd /var/www/mimic
sudo -u mimic bash -c "source venv/bin/activate && python migrations/migrate.py"
```

### 4. Виправити права

```bash
sudo chown -R mimic:mimic /var/www/mimic
sudo chmod 600 /var/www/mimic/.env
sudo chmod 600 /var/www/mimic/config.ini
```

### 5. Запустити сервіси

```bash
sudo systemctl start mimic
sudo systemctl start mimic-worker
sudo systemctl start mimic-bot

# Перевірити
sudo systemctl status mimic
```
