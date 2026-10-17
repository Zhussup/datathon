# Forte Vision

Интерфейс проверки кассовых операций по видео для ForteBank Datathon 2026.

Вся клиентская часть находится в папке [`frontend`](./frontend). Инструкция запуска и ограничения прототипа — в [`frontend/README.md`](./frontend/README.md).

```sh
cd frontend
npm ci
npm run dev
```

Минимальный API находится в [`backend`](./backend): загрузка видео и получение статуса задачи. Запуск — в [`backend/README.md`](./backend/README.md). Модель пока не подключена; frontend работает отдельно в деморежиме.
