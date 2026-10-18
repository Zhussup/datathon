# Сдача: Forte Vision (детекция нарушений кассовой дисциплины) — что передавать жюри

⚠ Перепроверить перед отправкой: туннель перезапускается с НОВЫМ URL. Живой адрес всегда в
`/home/zhus/datathon/cloudflared.log` на neuro (последняя строка `trycloudflare.com`). Проверка:
`curl -s -o /dev/null -w '%{http_code}' <URL>/` должно быть 200.

## Жюри (раздел 8 ТЗ, критично)
- **URL сервиса (UI):** `https://demographic-print-phentermine-sudden.trycloudflare.com`
- **URL API:** `<тот же URL>/api/v1/…`
- **X-API-Key:** `fv-dttn2026`
- UI: в шапке кнопка «API» → ввести ключ → выбрать .mov → «Анализ». Без ключа загрузка невозможна.

## Инструкция по запуску и использованию
Поставляется готовой (сервер `neuro`, все модели локально, без интернета после загрузки весов).
Всё в одном процессе: FastAPI (API + worker) отдаёт и React-UI (`/`), и JSON API.

Проверка API из терминала:
```bash
curl -X POST https://<URL>/api/v1/analyze -H "X-API-Key: fv-dttn2026" -F "file=@video_017.mov"
# → {"job_id": "..."} ; затем:
curl https://<URL>/api/v1/jobs/<job_id> -H "X-API-Key: fv-dttn2026"
# → status processing|done|failed; при done — verdict + violations[] по разделу 10 ТЗ
```

## Архитектура (кратко)
- **W2, детекция:** RF-DETR nano (7 классов примитивов, Apache-2.0) + COCO RF-DETRBase (person), 1 fps.
- **W3, факты:** зоны по глубине/столу, IoU-трекинг, гистерезис → FactTable на тиках 0.5 с
  (client_present, banknotes_on_desk, cashier_away, door_open, …, события handover/count_start/…),
  ghost-фильтр отражений в стекле.
- **Решение:** детерминированный движок `pipeline/` — 11 правил (order: порядок внутри визита;
  streak: инварианты всего ролика) над таблицей фактов; типы «признак, требует проверки» без
  надуманных НПА. Пороги — данные (Config), вердикт воспроизводим и объясним.
- **Нормативка:** только акты РК — Пост. НБ РК № 231 (29.11.2019, V1900019680) и № 14 (24.02.2020,
  V2000020075), точные пункты в `law.md`, проверены по adilet.zan.kz.

## Цифры (локальная сверка с labels.csv, окно ±10 с)
TP=17, FN=3, FP=12, TN=6 → recall 0.85, precision 0.59, F1 0.69 на 38 роликах.
Список правил + пункты: `rules_tree.html`, `law.md`.