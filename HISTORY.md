# История разработки Laedectra Helper Bot

## Описание проекта
Telegram-бот для поддержки покупателей GPS-трекера AK-39B. Бот предоставляет:
- Инструкции по подключению и использованию
- Решение типичных проблем
- Информацию о характеристиках устройства
- Админ-панель для редактирования контента

## Технологии
- Python 3.12
- python-telegram-bot 21.0
- JSON для хранения контента и конфигурации

## Структура файлов
```
laedectra_helper_bot/
├── bot.py           # Основной код бота
├── config.json      # Токен и пароль админки
├── content.json     # Контент бота (60+ разделов)
├── requirements.txt # Зависимости
├── .gitignore       # Игнорируемые файлы
└── HISTORY.md       # Этот файл
```

---

## Сессия 1: Создание и отладка

### Проблема: Админ-панель не отвечала после ввода пароля
**Симптомы:** После команды `/admin` и ввода пароля бот не реагировал.

**Диагностика:**
1. Добавлено подробное логирование в `admin_start`, `admin_auth`, `show_admin_menu`
2. Проверены процессы: `ps aux | grep bot.py`

**Причина:** Запущено несколько экземпляров бота одновременно. Telegram API выдавал ошибку:
```
Conflict: terminated by other getUpdates request
```

**Решение:**
```bash
pkill -9 -f "bot.py"
python bot.py
```

---

## Сессия 2: Деплой на VPS

### Данные сервера
- **Хостинг:** Timeweb
- **IP:** 89.169.0.55
- **OS:** Ubuntu 24.04 LTS
- **Путь к боту:** `/opt/laedectra_bot/`

### Шаги деплоя

1. **Подключение к серверу:**
```bash
ssh root@89.169.0.55
```

2. **Установка зависимостей:**
```bash
apt update
apt install -y python3-pip python3-venv
```

3. **Создание директории и загрузка файлов:**
```bash
mkdir -p /opt/laedectra_bot
scp bot.py config.json content.json requirements.txt root@89.169.0.55:/opt/laedectra_bot/
```

4. **Создание виртуального окружения:**
```bash
cd /opt/laedectra_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

5. **Создание systemd сервиса:**
```bash
cat > /etc/systemd/system/laedectra-bot.service << 'EOF'
[Unit]
Description=Laedectra Helper Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/laedectra_bot
ExecStart=/opt/laedectra_bot/venv/bin/python /opt/laedectra_bot/bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

6. **Запуск сервиса:**
```bash
systemctl daemon-reload
systemctl enable laedectra-bot
systemctl start laedectra-bot
```

### Команды управления ботом на сервере

```bash
# Статус
systemctl status laedectra-bot

# Перезапуск
systemctl restart laedectra-bot

# Остановка
systemctl stop laedectra-bot

# Логи (последние 50 строк)
journalctl -u laedectra-bot -n 50

# Логи в реальном времени
journalctl -u laedectra-bot -f
```

### Обновление бота на сервере
После изменений в коде:
```bash
scp bot.py content.json root@89.169.0.55:/opt/laedectra_bot/
ssh root@89.169.0.55 "systemctl restart laedectra-bot"
```

---

## Важные заметки

1. **Один экземпляр бота:** Нельзя запускать бота одновременно локально и на сервере — будет конфликт.

2. **Админ-панель:** Доступ через команду `/admin`, пароль в `config.json`.

3. **Автозапуск:** Бот автоматически перезапускается при падении (systemd Restart=always).

4. **Логирование:** Уровень DEBUG для отладки, можно изменить на INFO в продакшене.

---

## Дата последнего обновления
4 февраля 2026
