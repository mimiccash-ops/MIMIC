# 🔄 Команди для оновлення з GitHub

## На VPS (Linux) - Оновити файли з GitHub

### Базова команда (найпростіша):

```bash
cd /var/www/mimic
git pull
```

### Якщо є локальні зміни, які потрібно зберегти:

```bash
cd /var/www/mimic
git stash          # Зберегти локальні зміни
git pull           # Оновити з GitHub
git stash pop      # Повернути локальні зміни
```

### Якщо потрібно відкинути локальні зміни і взяти тільки з GitHub:

```bash
cd /var/www/mimic
git fetch origin
git reset --hard origin/main
```

⚠️ **Увага:** Це видалить всі локальні зміни!

---

## На Windows (локальна машина) - Оновити файли з GitHub

### Базова команда:

```powershell
cd "C:\Users\MIMIC Admin\Desktop\MIMIC v 4.0"
git pull
```

### Або через PowerShell скрипт:

```powershell
.\pull_from_github.ps1
```

---

## Повний процес оновлення на VPS

```bash
# 1. Перейти в директорію проекту
cd /var/www/mimic

# 2. Оновити файли з GitHub
git pull

# 3. Оновити Python залежності (якщо requirements.txt змінився)
source venv/bin/activate
pip install -r requirements.txt

# 4. Оновити Node.js залежності (якщо package.json змінився)
npm install
npm run build

# 5. Запустити міграції бази даних (якщо є нові)
python migrations/migrate.py

# 6. Перезапустити сервіси
sudo systemctl restart mimic
sudo systemctl restart mimic-worker
sudo systemctl restart mimic-bot
```

---

## Автоматичне оновлення (скрипт)

Створіть скрипт для автоматичного оновлення:

```bash
#!/bin/bash
# update_mimic.sh

cd /var/www/mimic

echo "🔄 Оновлення з GitHub..."
git pull

echo "📦 Оновлення Python залежностей..."
source venv/bin/activate
pip install -r requirements.txt --quiet

echo "🔨 Збірка фронтенду..."
npm install --silent
npm run build --silent

echo "🗄️  Запуск міграцій..."
python migrations/migrate.py

echo "🔄 Перезапуск сервісів..."
sudo systemctl restart mimic mimic-worker mimic-bot

echo "✅ Оновлення завершено!"
```

Зробити виконуваним:
```bash
chmod +x update_mimic.sh
```

Використання:
```bash
sudo ./update_mimic.sh
```

---

## Перевірка статусу

### Подивитися, чи є оновлення на GitHub:

```bash
cd /var/www/mimic
git fetch
git status
```

### Подивитися, що змінилося:

```bash
git log HEAD..origin/main
```

### Подивитися різницю:

```bash
git diff HEAD origin/main
```

---

## Часті помилки та рішення

### Помилка: "Your local changes would be overwritten"

**Рішення:**
```bash
git stash
git pull
git stash pop
```

### Помилка: "Please commit your changes"

**Рішення:**
```bash
# Зберегти зміни
git add .
git commit -m "Local changes before pull"

# Або відкинути зміни
git reset --hard
git pull
```

### Помилка: "Permission denied"

**Рішення:**
```bash
sudo chown -R mimic:mimic /var/www/mimic
```

---

## Швидкі команди

| Дія | Команда |
|-----|---------|
| Оновити файли | `git pull` |
| Перевірити статус | `git status` |
| Подивитися зміни | `git log origin/main..HEAD` |
| Відкинути локальні зміни | `git reset --hard origin/main` |
| Зберегти локальні зміни | `git stash` |
| Повернути збережені зміни | `git stash pop` |

---

## Автоматичне оновлення через Cron

Додати в crontab для автоматичного оновлення:

```bash
# Редагувати crontab
crontab -e

# Оновлювати кожен день о 3:00 ранку
0 3 * * * cd /var/www/mimic && git pull && systemctl restart mimic
```
