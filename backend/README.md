# Backend

Python 3.12+, FastAPI. Из корня репозитория:

Linux/macOS:
```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
API_KEY='your-local-key' .venv/bin/python -m uvicorn main:app --reload
```

Windows PowerShell:
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
| POST | `/api/v1/analyze` | Multipart-поле `file`, MOV/MP4 до 200 МБ. Файл сохраняется на диск (`storage/<job_id>/video.mov`). Ответ `202`: `{"job_id": "..."}`. |
| GET | `/api/v1/jobs/{job_id}` | `{"job_id", "status": processing\|done\|failed}`; при `done` — вердикт по схеме раздела 10 ТЗ; при `failed` — `error`; `404`, если задача неизвестна. |

Как это устроено:

- `main.py` — приём файла, хранилище на диске, проверка ключа; сама обработка идёт в `worker.py`.
- `worker.py` — очередь задач и N потоков (`WORKER_COUNT`), бюджет обработки `PROCESS_BUDGET_SEC`
  (сек по умолчанию 270 — запас до лимита 5 минут, FAQ 14); превышение — честный `failed`, без частичных вердиктов.
- `perception.py` — заглушка перцепции (W2/W3): пока нейросеть не подключена, задание падает в `failed`
  с понятной ошибкой. Переменная `PIPELINE_DEMO_FACTS` подменяет перцепцию фикстурой фактов
  (`fixtures/*.json`) — так можно гонять полный цикл API до готовности детектора.
- Кадры-доказательства вырезаются из сохранённого видео через OpenCV (JPEG, качество 85) и кладутся
  в `image_base64`; кадр, который не удалось вырезать, не выдаётся.

Демо-прогон через полный HTTP-цикл (вердикт R2 на фикстуре Х-15):

```bash
API_KEY=test-key PIPELINE_DEMO_FACTS=$(pwd)/../fixtures/X-15.json \
  .venv/bin/python -m uvicorn main:app &
# затем POST .mov → GET job → done с violation / type "Безнадзорные ценности" / timecode 15.0
```

Офлайн-сборка того же ответа без сервера (проверка движка и вырезки кадров на реальном видео):

```bash
python3 scripts/render_result.py fixtures/X-15.json open/videos/Х-15.mov result.json
```

Проверка:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest -v
```

Задачи хранятся в памяти одного процесса до перезапуска. Frontend работает отдельно.