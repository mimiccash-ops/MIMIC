# 🔍 Знайти директорію проекту

## Проблема
`/root/mimic` не є git репозиторієм або docker-compose.yml не знайдено.

## Рішення

### 1. Знайти правильну директорію:

```bash
# Перевірити, де знаходиться проект
find / -name "docker-compose.yml" -type f 2>/dev/null | grep -i mimic
find / -name ".git" -type d 2>/dev/null | grep -i mimic
find / -name "install_vps.sh" -type f 2>/dev/null

# Або перевірити стандартні місця
ls -la /var/www/mimic
ls -la /opt/mimic
ls -la /root/mimic
ls -la ~/mimic
```

### 2. Якщо проект в `/var/www/mimic` (стандартне місце):

```bash
cd /var/www/mimic

# Оновити код
git pull

# Оновити Docker
docker compose down
docker compose build --no-cache
docker compose up -d
docker compose run --rm web python migrations/migrate.py
```

### 3. Якщо проект в іншому місці:

```bash
# Знайти директорію
PROJECT_DIR=$(find / -name "docker-compose.yml" -type f 2>/dev/null | head -1 | xargs dirname)

# Перейти в неї
cd "$PROJECT_DIR"

# Оновити
git pull
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 4. Якщо це не git репозиторій:

```bash
# Ініціалізувати git або клонувати знову
cd /var/www/mimic  # або ваша директорія
git init
git remote add origin https://github.com/mimiccash-ops/MIMIC.git
git pull origin main
```

### 5. Перевірити Docker Compose:

```bash
# Перевірити, чи встановлено docker compose
docker compose version

# Перевірити, чи є docker-compose.yml
ls -la docker-compose.yml

# Якщо використовується старий docker-compose
docker-compose version
docker-compose down
docker-compose up -d --build
```
