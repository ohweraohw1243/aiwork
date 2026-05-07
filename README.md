# Личный кабинет клиента | Проект «ИИ и промптинг»

Это готовая архитектура веб-приложения для клиента салона красоты.

## Функционал
1. Просмотр активных записей.
2. Просмотр истории визитов.
3. Доступные свободные окна.
4. **Умное предложение (AI-генерация)**: Использует API Groq (llama3-8b-8192) для генерации персонализированных предложений на основе истории визитов клиента. Этот пункт демонстрирует промптинг.

## Технологии
- **Backend:** Python / Flask
- **AI Integrarion:** Нейросеть LLaMA3 через Python SDK `groq` и системный промпт
- **Шрифты и UI:** HTML5 + Tailwind CSS (via CDN) + Javascript для асинхронного подтягивания ответа.

## Как запустить проект

Убедитесь, что у вас установлен Python (3.x).

1. Установите зависимости:
```bash
pip3 install -r requirements.txt
```

2. Запустите Flask-сервер:
```bash
python3 app.py
```

3. Откройте в браузере: `http://127.0.0.1:5001`

## Как выложить на Render
1. Залейте код в GitHub.
2. Откройте [Render](https://render.com) и создайте `New +` -> `Web Service`.
3. Выберите ваш GitHub-репозиторий.
4. Укажите:
  - `Environment`: `Python`
  - `Build Command`: `pip install -r requirements.txt`
  - `Start Command`: `gunicorn app:app`
5. Добавьте переменные окружения в Render:
  - `GROQ_API_KEY` - ваш ключ Groq
  - `FLASK_SECRET_KEY` - любой длинный случайный секрет
  - `DATABASE_URL` - URL PostgreSQL, если вы подключаете отдельную базу
6. Если базы еще нет, можно сначала запустить проект на локальном SQLite, а потом подключить PostgreSQL в Render и вставить `DATABASE_URL`.

Если хотите использовать Render PostgreSQL, сначала создайте `New +` -> `PostgreSQL`, затем вставьте выданный `Internal Database URL` в `DATABASE_URL` у Web Service.
