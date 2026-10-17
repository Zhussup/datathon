# Backend

Python 3.12+, FastAPI. Из корня репозитория, PowerShell:

```powershell
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
$env:API_KEY = 'your-local-key'
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

API: http://127.0.0.1:8000. Документация: http://127.0.0.1:8000/docs.

Оба маршрута требуют заголовок `X-API-Key`, совпадающий с переменной окружения `API_KEY`.

| Метод | Путь | Результат |
| --- | --- | --- |
| POST | `/api/v1/analyze` | Multipart-поле `file`, MOV/MP4 до 200 МБ. Ответ `202`: `{"job_id": "..."}`. |
| GET | `/api/v1/jobs/{job_id}` | Статус задачи или `404`, если задача не найдена. |

Модель пока не подключена: созданная задача возвращает `status: "failed"` и `error: "Analysis model is not configured"`. Вердикт не формируется. Файл после проверки загрузки закрывается и не сохраняется. Задачи хранятся в памяти одного процесса до перезапуска. Frontend пока работает отдельно в деморежиме.

Проверка:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m unittest -v
```
