# 🐳 Оновлення MIMIC в Docker

## ⚠️ Важливо про ваші команди

Ваші команди:
```bash
cd /root/mimic
git pull origin main
docker compose down -v          # ⚠️ ПРОБЛЕМА: -v видаляє volumes!
docker compose up -d --build
```

### Проблема з `docker compose down -v`:

Флаг `-v` (або `--volumes`) **видаляє всі volumes**, включаючи:
- `postgres_data` - база даних PostgreSQL (всі дані!)
- `redis_data` - дані Redis
- `grafana_data` - налаштування Grafana
- `prometheus_data` - метрики Prometheus

**Це видалить всі ваші дані!** ❌

---

## ✅ Правильний спосіб оновлення

### Варіант 1: Використати скрипт (рекомендовано)

```bash
cd /root/mimic
chmod +x update_docker.sh
./update_docker.sh
```

### Варіант 2: Вручну (безпечно)

```bash
cd /root/mimic

# 1. Оновити код
git pull origin main
# або просто: git pull

# 2. Зупинити контейнери БЕЗ видалення volumes
docker compose down
# ⚠️ НЕ використовуйте: docker compose down -v

# 3. Перебудувати образи (якщо змінився код)
docker compose build --no-cache

# 4. Запустити контейнери
docker compose up -d

# 5. Запустити міграції (якщо потрібно)
docker compose run --rm web python migrations/migrate.py
```

---

## 🔄 Різні сценарії оновлення

### Швидке оновлення (тільки код, без перебудови)

```bash
cd /root/mimic
git pull
docker compose restart web worker
```

### Повне оновлення (з перебудовою образів)

```bash
cd /root/mimic
git pull
docker compose down              # БЕЗ -v!
docker compose build --no-cache
docker compose up -d
docker compose run --rm web python migrations/migrate.py
```

### Оновлення тільки образів (без зміни коду)

```bash
cd /root/mimic
docker compose pull
docker compose up -d
```

---

## 📋 Покрокова інструкція

### 1. Перевірити оновлення

```bash
cd /root/mimic
git fetch
git status
```

### 2. Оновити код

```bash
git pull origin main
```

### 3. Зупинити контейнери

```bash
docker compose down
# ⚠️ НЕ використовуйте -v або --volumes
```

### 4. Перебудувати образи (якщо потрібно)

```bash
# Якщо змінився код Python/залежності
docker compose build --no-cache

# Або якщо тільки оновлення образів
docker compose pull
```

### 5. Запустити контейнери

```bash
docker compose up -d
```

### 6. Перевірити статус

```bash
docker compose ps
docker compose logs -f web
```

### 7. Запустити міграції (якщо є зміни в БД)

```bash
docker compose run --rm web python migrations/migrate.py
```

---

## 🛡️ Безпека даних

### Що зберігається в volumes:

- ✅ База даних PostgreSQL (`postgres_data`)
- ✅ Дані Redis (`redis_data`)
- ✅ Налаштування Grafana (`grafana_data`)
- ✅ Метрики Prometheus (`prometheus_data`)

### Коли використовувати `-v`:

**ТІЛЬКИ** якщо ви хочете **повністю видалити всі дані** і почати з нуля:

```bash
# ⚠️ ЦЕ ВИДАЛИТЬ ВСІ ДАНІ!
docker compose down -v
docker volume prune  # Додатково видалить volumes
```

---

## 🔍 Перевірка після оновлення

```bash
# Перевірити статус контейнерів
docker compose ps

# Перевірити логи
docker compose logs -f web
docker compose logs -f worker

# Перевірити здоров'я
docker compose ps | grep -E "Up|healthy"
```

---

## 🚨 Якщо щось пішло не так

### Відкотити до попередньої версії:

```bash
cd /root/mimic
git log --oneline -5          # Подивитися коміти
git checkout <commit-hash>    # Повернутися до попереднього коміту
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Перезапустити контейнер:

```bash
docker compose restart web
docker compose restart worker
```

### Переглянути помилки:

```bash
docker compose logs web | tail -50
docker compose logs worker | tail -50
```

---

## 📝 Швидка довідка

| Дія | Команда |
|-----|---------|
| Оновити код | `git pull` |
| Зупинити (безпечно) | `docker compose down` |
| Зупинити (видалити дані) | `docker compose down -v` ⚠️ |
| Перебудувати образи | `docker compose build --no-cache` |
| Запустити | `docker compose up -d` |
| Перезапустити | `docker compose restart web` |
| Логи | `docker compose logs -f web` |
| Статус | `docker compose ps` |
| Міграції | `docker compose run --rm web python migrations/migrate.py` |

---

## ✅ Рекомендований процес

```bash
# Використати скрипт (найбезпечніше)
cd /root/mimic
./update_docker.sh
```

Або вручну:
```bash
cd /root/mimic
git pull
docker compose down              # БЕЗ -v!
docker compose build --no-cache
docker compose up -d
docker compose run --rm web python migrations/migrate.py
```

**Головне:** Ніколи не використовуйте `-v` якщо не хочете видалити дані! 🛡️
