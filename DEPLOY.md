# DEPLOY.md — деплой Forte Vision на свой сервер с публичным URL

Путь сдачи W5/W6: сервис крутится на `neuro`, жюри получает **публичный URL + ключ**
(FAQ 23, критерий 6 «Готовность продукта», API-раздел 10 ТЗ). Всё работает локально
на сервере — наружу смотрит только nginx с TLS; никаких облачных вызовов нет.

Ниже все команды для сервера `neuro` (`sadmin@neuro`), рабочая папка
`/home/zhus/datathon`. Замени плейсхолдеры:

| Плейсхолдер | Смыл | Пример |
| --- | --- | --- |
| `forte.example.com` | твоя доменная запись | `forte.mydomain.kz` |
| `1.2.3.4` | публичный IPv4 сервера | |
| `<ключ>` | сгенерированный API-ключ | |

---

## Целевая схема

```
жюри / браузер
   │  https://forte.example.com
   ▼
nginx (:443, TLS Let's Encrypt) ── статика фронтенда (/var/www/forte-vision)
   │  /api/*, /docs → proxy_pass
   ▼
uvicorn (127.0.0.1:8000) FastAPI — форк приёма файла, X-API-Key
   │  in-process очередь задач (WORKER_COUNT потоков)
   ▼
perception: infer_w2.py (W2-детектор + COCO person) → w3_facts.py   [GPU 0]
   ▼
pipeline.engine (детерминированные правила) → вердикт + кадры (OpenCV)
```

Вторая карта (GPU 1) — llama-server (LLM-отчёт), его надо перевести на GPU 1
до старта (см. шаг 3).

---

## 0. Пред-условия

- [ ] Репозиторий на сервере актуален: `/home/zhus/datathon` (код `backend/`,
      `pipeline/`, `scripts/`, веса `w2_nano/checkpoint_best_ema.pth`).
- [ ] venv сервера жив: `/home/zhus/datathon/venv` со свежим torch cu128 ≥ 2.7,
      rfdetr, supervision (`scripts/setup_neuro.sh` уже ставил).
- [ ] Домен в твоём распоряжении (A-запись можно менять).
- [ ] Свободно ≥ 25 ГБ на диске под storage + torch-кэш.

## 1. DNS

Заведи A-запись (TTL заранее 300 с, чтобы потом быстро перебросить):

```
forte.example.com.   IN  A   1.2.3.4
```

Проверка (снаружи сервера): `dig +short forte.example.com` → `1.2.3.4`.

**Если сервер за NAT** (внешний IP в `curl -4 ifconfig.me` не совпадает с адресом
на интерфейсе): пробросить 80 и 443 TCP на машину в настройках роутера /
попросить у админа. Без этого жюри не доберётся — FAQ 23 требует живой URL.

## 2. Публичная достижимость

```bash
curl -4 ifconfig.me                      # какой IP видит мир
ip -4 addr | grep inet                   # какой IP на интерфейсе
sudo ss -tlnp | grep -E ':80|:443'       # заняты ли порты
```

Наружу открываем только 22/80/443. Uvicorn будет слушать 127.0.0.1:8000 —
его наружу не выставляем: API-ключ должен проверяться за nginx, у которого
один TLS-вход.

## 3. GPU: llama-server → GPU 1, детектор → GPU 0

Перед стартом сервиса обе карты должны быть размиссены (сейчас llama-server
сидит на обеих). Переводим его на вторую:

```bash
# найти процесс llama-server, перезапустить с одной картой:
pgrep -a llama-server
# пример перезапуска (подставь свои флаги запуска!):
CUDA_VISIBLE_DEVICES=1 <исходная команда llama-server ...> &
```

В unit-файле llama-server — то же самое (`Environment=CUDA_VISIBLE_DEVICES=1`).
Детектор сервиса получит GPU 0 через `CUDA_VISIBLE_DEVICES=0` в env-файле
(шаг 5). Проверка: `nvidia-smi` — GPU 0 почти пуст, GPU 1 — llama-server.

COCO-веса для person-детекции **обязательны**: без них перцепция отдаёт факты
без клиентов/кассира, и order-правила (R1/R4/R6/R10) молчат.

```bash
ls -lh /home/zhus/datathon/weights/rfdetr_base_coco.pth
# нет — скачай один раз (~120 МБ) и перенеси в weights/:
#   venv/bin/python -c "from rfdetr import RFDETRBase; RFDETRBase(pretrain_weights='coco')"
#   find ~ /home/sadmin -name "*.pth" -size +100M -newer /tmp 2>/dev/null | head   # найди, куда лег файл
#   mv <файл> /home/zhus/datathon/weights/rfdetr_base_coco.pth
```

## 4. Зависимости API в существующий venv

Перцепция запускает `scripts/infer_w2.py` через `sys.executable` — это тот же
интерпретатор, что у uvicorn, поэтому **один venv нужен для всего** (torch +
fastapi вместе):

```bash
cd /home/zhus/datathon
/home/zhus/datathon/venv/bin/python -c "import cv2" \
  && echo "cv2 есть, opencv из requirements можно не ставить" \
  || venv/bin/pip3 install opencv-python-headless
venv/bin/pip3 install fastapi==0.143.3 uvicorn==0.54.0 python-multipart==0.0.32
```

Смоук без GPU (весь цикл API на фикстуре фактов, как в `backend/README.md`):

```bash
cd /home/zhus/datathon/backend
API_KEY=smoke-key \
PIPELINE_DEMO_FACTS=$(pwd)/../fixtures/X-15.json \
  /home/zhus/datathon/venv/bin/python -m uvicorn main:app --port 8000 &
# POST любого .mov → GET job → done: violation / «Безнадзорные ценности» / 15.0
```

Быстрая проверка движка: `venv/bin/python scripts/run_sanity.py` → все фикстуры зелёные.

## 5. Env-файл сервиса

Сгенерируй ключ (команда команды, жюри отдадим именно его):

```bash
openssl rand -hex 32      # результат → в env-файл и в блок «Передача жюри» ниже
```

`/etc/forte-vision.env` (chmod 600 root:root, читает только systemd):

```ini
API_KEY=<ключ>
CORS_ORIGINS=https://forte.example.com
STORAGE_DIR=/home/zhus/datathon/storage
WORKER_COUNT=1              # начни с 1; к жюрейскому прогону подними до 2–3,
                            # если VRAM позволяет две параллельные инференции (по 12 ГБ на карте)
PROCESS_BUDGET_SEC=270      # запас до лимита 5 мин (FAQ 14)
CUDA_VISIBLE_DEVICES=0      # детектор на первой карте; LLM на второй
W2_THRESHOLD=0.4
PERSON_THRESHOLD=0.5
PERCEPTION_TMP=/tmp
# W2_WEIGHTS=/home/zhus/datathon/w2_nano/checkpoint_best_ema.pth   # дефолт сам найдётся
# COCO_WEIGHTS=/home/zhus/datathon/weights/rfdetr_base_coco.pth
```

⚠️ `W2_WEIGHTS`/`COCO_WEIGHTS` не раскомментированы, только если пути дефолтные —
иначе убедись, что файл по указанному пути существует.

## 6. systemd unit сервиса

⚠️ **`--workers` = ровно 1.** Хранилище задач воркера в памяти процесса
(`worker.JobStore`): два uvicorn-воркера разорвали бы очередь и поллинг `GET
/jobs/{job_id}`. Масштабируем не процессами, а `WORKER_COUNT`.

`/etc/systemd/system/forte-api.service`:

```ini
[Unit]
Description=Forte Vision API (fastapi + worker + perception)
After=network.target

[Service]
User=<владелец /home/zhus/datathon>       # обычно sadmin
WorkingDirectory=/home/zhus/datathon/backend
EnvironmentFile=/etc/forte-vision.env
ExecStart=/home/zhus/datathon/venv/bin/python -m uvicorn main:app \
    --host 127.0.0.1 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now forte-api
systemctl status forte-api --no-pager
journalctl -u forte-api -n 30 --no-pager
```

## 7. nginx

`/etc/nginx/sites-available/forte-vision`:

```nginx
upstream forte_api { server 127.0.0.1:8000; fail_timeout=0; }

server {
    listen 80;
    server_name forte.example.com;

    client_max_body_size 250m;        # бэкенд сам ограничит 200 МБ (413)
    client_body_timeout 120s;

    # статика фронтенда (заливка на шаге 9)
    root /var/www/forte-vision;
    index index.html;

    # API и Swagger — на бэкенд
    location ~ ^/(api|docs|openapi\.json)(/|$) {
        proxy_pass http://forte_api;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_request_buffering off;   # стримить 200 МБ на бэкенд, не в диск nginx
        proxy_read_timeout 300s;
    }

    location / {
        try_files $uri /index.html;   # SPA-роуты фронтенда
    }
}
```

```bash
sudo ln -sf /etc/nginx/sites-available/forte-vision /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 8. TLS

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d forte.example.com          # редирект на https — выбрать
sudo certbot renew --dry-run                       # автопродление работает
```

Если порты 80/443 закрыты извне — certbot проверку не пройдёт: сначала шаг 2.

## 9. Фронтенд: сборка и заливка

Собирать локально (Node 22.12+ уже стоит), на сервер Node не нужен:

```bash
cd frontend
npm ci
VITE_API_KEY='' npm run build        # ключ НЕ пекём (см. ниже)
rsync -az --delete dist/ sadmin@neuro:/tmp/forte-dist/
ssh sadmin@neuro "sudo rsync -az --delete /tmp/forte-dist/ /var/www/forte-vision/"
```

Про `VITE_API_KEY` (ключ в JS-бандле читается любым посетителем сайта):

- **Не пекём (по умолчанию)** — сайт показит ДЕМО-режим; ключ вводится через
  `localStorage["forte-api-key"]` в консоли браузера. Ключ жюри отдаём отдельно
  от URL, вместе с ним всё видно.
- **Пекём** — `VITE_API_KEY=<ключ> npm run build`: UI живёт в полном режиме без
  настроек. Плюс: критерий 6 смотрит мгновенно. Минус: ключ в публичном бандле,
  любой сможет гонять очередь видео. Годится, если финальный прогон уже прошёл
  или ты осознанно допускаешь риск; в любом случае ключ уходит жюри открыто.

Проверка: открыть `https://forte.example.com`, загрузить MOV — должен пройти
полный цикл (или внятная ошибка, не «обработано» навечно).

## 10. Файрвол

```bash
sudo ufw allow 22/tcp; sudo ufw allow 80,443/tcp; sudo ufw enable
sudo ufw status
```

## 11. Смоуки (чек-лист PLAN, внешний прогон)

```bash
# 1. Version — сколько правил и какой бюджет
curl -s https://forte.example.com/api/v1/version -H "X-API-Key: <ключ>" | jq

# 2. Отказ без ключа (401) и с пустым API_KEY на сервере (503 «not configured»)
curl -s -o /dev/null -w '%{http_code}\n' https://forte.example.com/api/v1/version

# 3. Полный цикл: реальный .mov → job_id → done за ≤ 300 c
JOB=$(curl -s -X POST https://forte.example.com/api/v1/analyze \
      -H "X-API-Key: <ключ>" -F "file=@Х-15.mov" | jq -r .job_id)
time curl -s https://forte.example.com/api/v1/jobs/$JOB -H "X-API-Key: <ключ>" | jq '.status, .verdict'

# 4. Мусор на входе → быстрый 415/failed, не висит
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://forte.example.com/api/v1/analyze \
     -H "X-API-Key: <ключ>" -F "file=@not-video.mov"
```

Сверить ответ с разделом 10 ТЗ: `verdict`, `violations[]` с
`type/timecode_sec/description/evidence_frames[1–3]`, пустой список на чистом
видео. Прогнать **три** ролика из другой сети (телефон/мобильный интернет),
замерить время — критерий FAQ 23 (публичный URL живой) + FAQ 14 (≤ 5 мин).

## 12. Эксплуатация

- **Обновление кода**: `git pull` → `sudo systemctl restart forte-api` → смоук
  шага 11.1; фронт — повторить шаг 9.
- **Рестарт сбрасывает очередь и результаты** (job store в памяти): рестартить
  только в паузу, не во время жюрейского поллинга.
- **Чистка storage** (видео ~29 МБ × приёмы; хранит на инспекцию) — раз в сутки:
  ```cron
  17 3 * * * find /home/zhus/datathon/storage -mindepth 1 -type d -mtime +2 -exec rm -rf {} +
  ```
- **Логи**: `journalctl -u forte-api -f`; хвосты подпроцессов перцепции падают в
  тот же журнал (`[perception] infer_w2 …`).
- **Веса обновились** (новый чекпоинт W2): заменить `w2_nano/checkpoint_best_ema.pth`
  или прописать `W2_WEIGHTS` в env-файле → `systemctl restart forte-api`.

## Передача жюри (W6)

Отправить организаторам:

1. **API-URL**: `https://forte.example.com/api/v1/analyze` (поле `file`, .mov/.mp4)
2. **Проверка результата**: `GET https://forte.example.com/api/v1/jobs/{job_id}`
3. **Ключ**: заголовок `X-API-Key: <ключ>`
4. UI: `https://forte.example.com`

Шаблон для жюри (можно вставить в письмо):

```
POST https://forte.example.com/api/v1/analyze
  Header: X-API-Key: <ключ>
  Body:   multipart/form-data, поле file (.mov, до 200 МБ)
  → {"job_id": "..."}   # 202
GET https://forte.example.com/api/v1/jobs/<job_id>
  Header: X-API-Key: <ключ>
  → status: processing|done|failed; при done — вердикт по разделу 10 ТЗ
```

## Известные особенности (не чинить в последний час)

| Симптом | Причина |
| --- | --- |
| `503 "API_KEY is not configured"` | env-файл не подхватился (`systemctl show forte-api -p EnvironmentFiles`) |
| Все видеов `failed: PerceptionUnavailable` с «не найдены W2-веса» | нет `w2_nano/checkpoint_best_ema.pth` на сервере; задать `W2_WEIGHTS` |
| Вердикты есть, но все «клиента не видели» | нет COCO-весов — person не детектится, order-правила молчат (шаг 3) |
| `413` nginx на загрузке | `client_max_body_size` меньше файла / не перечитан конфиг |
| Второй процесс uvicorn ломает поллинг | job store в памяти; `--workers` держим 1, параллелизм — через `WORKER_COUNT` |
| GPU занят, CUDA OOM | llama-server не переехал на GPU 1 (шаг 3) |