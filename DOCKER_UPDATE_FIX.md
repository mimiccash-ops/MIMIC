# 🔧 Виправлення помилки Telegram в Docker

## Проблема
Docker контейнер використовує стару версію `config.py` без виправлення для опціональної секції Telegram.

## Рішення

### 1. Перебудувати образи з новим кодом:

```bash
cd /var/www/mimic

# Переконатися, що код оновлено
git pull

# Зупинити контейнери
docker compose down

# Перебудувати образи (важливо!)
docker compose build --no-cache

# Запустити
docker compose up -d

# Запустити міграції
docker compose run --rm web python migrations/migrate.py
```

### 2. Або додати секцію [Telegram] в config.ini:

```bash
cd /var/www/mimic
nano config.ini
```

Додайте в кінець файлу:

```ini
[Telegram]
bot_token = 
chat_id = 
enabled = False
disable_polling = False
polling_startup_delay = 30
```

Збережіть: `Ctrl+O`, `Enter`, `Ctrl+X`

### 3. Перезапустити контейнери:

```bash
docker compose restart web worker
docker compose run --rm web python migrations/migrate.py
```

---

## Швидке виправлення (рекомендовано):

```bash
cd /var/www/mimic
git pull
docker compose down
docker compose build --no-cache web worker
docker compose up -d
docker compose run --rm web python migrations/migrate.py
```

---

## Перевірка

```bash
# Перевірити версію config.py в контейнері
docker compose exec web grep -A 5 "if config.has_section('Telegram')" /app/config.py

# Якщо видно "if config.has_section('Telegram')" - код оновлено правильно
```
