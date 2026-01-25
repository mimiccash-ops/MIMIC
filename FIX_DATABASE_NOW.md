# 🔧 Швидке виправлення DATABASE_URL

## Проблема
DATABASE_URL все ще вказує на `brain_capital` замість `mimic_user`.

## Рішення

Виконайте на VPS:

```bash
cd /var/www/mimic

# Варіант 1: Виправити вручну
sudo nano .env
```

Знайдіть рядок:
```
DATABASE_URL=postgresql://brain_capital:your-db-password@localhost:5432/brain_capital
```

Замініть на:
```
DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db
```

Збережіть: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Або використати команду:

```bash
cd /var/www/mimic

# Видалити старий рядок і додати новий
sudo sed -i '/^DATABASE_URL=/d' .env
echo "DATABASE_URL=postgresql://mimic_user:bZNOkq0dXC2kD03HLjlHTlp9P@localhost:5432/mimic_db" >> .env

# Перевірити
grep DATABASE_URL .env
```

---

## Після виправлення:

```bash
# Запустити міграції
cd /var/www/mimic
source venv/bin/activate
python migrations/migrate.py
```
