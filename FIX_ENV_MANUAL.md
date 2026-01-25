# 🔧 Виправлення .env файлу вручну

## Проблема
DATABASE_URL злипся з попереднім рядком через відсутність нового рядка.

## Рішення

Виконайте на VPS:

```bash
cd /var/www/mimic

# 1. Виправити злипся рядок
sudo sed -i 's/START_MODE=dockerDATABASE_URL=/START_MODE=docker\nDATABASE_URL=/g' .env

# 2. Видалити всі старі DATABASE_URL рядки
sudo sed -i '/^DATABASE_URL=/d' .env

# 3. Додати правильний DATABASE_URL на новому рядку
echo "" >> .env
echo "DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db" >> .env

# 4. Перевірити
grep "^DATABASE_URL=" .env
```

Має показати:
```
DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db
```

## Або через nano (простіше):

```bash
cd /var/www/mimic
sudo nano .env
```

1. Знайдіть рядок `START_MODE=dockerDATABASE_URL=...`
2. Замініть на два окремі рядки:
   ```
   START_MODE=docker
   DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db
   ```
3. Збережіть: `Ctrl+O`, `Enter`, `Ctrl+X`

## Після виправлення:

```bash
# Запустити міграції
cd /var/www/mimic
source venv/bin/activate
python migrations/migrate.py
```

Тепер має показати PostgreSQL замість SQLite!
